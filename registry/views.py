from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Prefetch
from django.shortcuts import render, redirect
from django.utils import timezone

from .forms import RecordCreateForm
from .models import Attachment, AttachmentType, Record, RecordStatus


def _status_ui(expiry_date, today):
    """
    For table/front-end filters: valid | expiring | expired
    - expired: expiry_date < today
    - expiring: today <= expiry_date <= today+30
    - valid: expiry_date > today+30
    """
    if not expiry_date:
        return "valid"
    if expiry_date < today:
        return "expired"
    if expiry_date <= (today + timedelta(days=30)):
        return "expiring"
    return "valid"


def _require_org(request):
    """
    Enforce tenant isolation: user must belong to an organization.
    Returns organization or None (and sets a user-facing message).
    """
    org = getattr(request.user, "organization", None)
    if not org:
        messages.error(request, "Your account is not assigned to an Organization. Please contact admin.")
        return None
    if hasattr(org, "is_active") and not org.is_active:
        messages.error(request, "Your Organization is inactive. Please contact admin.")
        return None
    return org


@login_required
def home(request):
    today = timezone.localdate()
    soon_limit = today + timedelta(days=30)

    user = request.user
    is_global_admin = bool(getattr(user, "can_view_all_orgs", False))

    # ✅ ADMIN role sees ALL orgs
    if is_global_admin:
        base_qs = Record.objects.all().exclude(status=RecordStatus.ARCHIVED)
        org_missing = False
    else:
        org = _require_org(request)
        if not org:
            return render(
                request,
                "license-template/home.html",
                {
                    "total_count": 0,
                    "expiring_soon_count": 0,
                    "expired_count": 0,
                    "valid_count": 0,
                    "records": [],
                    "org_missing": True,
                    "today": today,
                    "soon_limit": soon_limit,
                },
            )

        base_qs = Record.objects.filter(organization=org).exclude(status=RecordStatus.ARCHIVED)
        org_missing = False

    # ✅ KPI (Aligned with your cards)
    stats = base_qs.aggregate(
        total_records=Count("id"),
        expiring_soon=Count("id", filter=Q(expiry_date__gte=today, expiry_date__lte=soon_limit)),
        expired=Count("id", filter=Q(expiry_date__lt=today)),
        valid_not_expired=Count("id", filter=Q(expiry_date__gte=today)),
    )

    # Attachments prefetch (efficient)
    att_qs = (
        Attachment.objects.filter(file_type__in=[AttachmentType.EVIDENCE, AttachmentType.CERTIFICATE_COPY])
        .only("id", "record_id", "file", "file_type", "created_at")
        .order_by("-created_at")
    )

    # ✅ For global admin we also select organization for display
    records_qs = (
        base_qs.select_related("owner", "organization")
        .prefetch_related(Prefetch("attachments", queryset=att_qs, to_attr="prefetched_attachments"))
        .only(
            "id",
            "title",
            "expiry_date",
            "owner__username",
            "owner__first_name",
            "owner__last_name",
            "organization__name",
        )
        .order_by("expiry_date", "title")[:200]
    )

    def _is_image(name: str) -> bool:
        s = (name or "").lower()
        return s.endswith((".jpg", ".jpeg", ".png", ".webp"))

    rows = []
    for r in records_qs:
        if r.expiry_date:
            days_left = (r.expiry_date - today).days
            status_ui = _status_ui(r.expiry_date, today)
        else:
            days_left = None
            status_ui = "valid"

        # owner display
        if getattr(r, "owner_id", None):
            full = f"{(r.owner.first_name or '').strip()} {(r.owner.last_name or '').strip()}".strip()
            owner_name = full or (r.owner.username or "—")
        else:
            owner_name = "—"

        # best preview attachment
        preview_url = ""
        atts = getattr(r, "prefetched_attachments", []) or []
        chosen = None

        # 1) evidence image first
        for a in atts:
            if a.file_type == AttachmentType.EVIDENCE and a.file and _is_image(getattr(a.file, "name", "")):
                chosen = a
                break

        # 2) then any evidence
        if not chosen:
            for a in atts:
                if a.file_type == AttachmentType.EVIDENCE and a.file:
                    chosen = a
                    break

        # 3) then certificate copy
        if not chosen:
            for a in atts:
                if a.file_type == AttachmentType.CERTIFICATE_COPY and a.file:
                    chosen = a
                    break

        if chosen and chosen.file:
            try:
                preview_url = chosen.file.url
            except Exception:
                preview_url = ""

        rows.append(
            {
                "id": r.id,
                "title": r.title,
                "owner_name": owner_name,
                "expiry_date": r.expiry_date,
                "days_left": days_left,
                "status_ui": status_ui,   # expired/expiring/valid (for front-end filter)
                "preview_url": preview_url,
                # ✅ shown only for ADMIN in template (optional)
                "org_name": getattr(getattr(r, "organization", None), "name", ""),
            }
        )

    return render(
        request,
        "license-template/home.html",
        {
            "total_count": stats["total_records"] or 0,
            "expiring_soon_count": stats["expiring_soon"] or 0,
            "expired_count": stats["expired"] or 0,
            "valid_count": stats["valid_not_expired"] or 0,  # ✅ Valid = Not expired
            "records": rows,
            "org_missing": org_missing,
            "today": today,
            "soon_limit": soon_limit,
            # ✅ template can use this to show org column
            "is_global_admin": is_global_admin,
        },
    )


@login_required
def create_record(request):
    user = request.user
    is_global_admin = bool(getattr(user, "can_view_all_orgs", False))

    # ✅ Non-admin must have org
    if not is_global_admin:
        org = _require_org(request)
        if not org:
            return redirect("registry:home")
    else:
        # ADMIN can still create records, but by default we keep using his org if exists
        # (If you want ADMIN to choose organization in the form, tell me and I’ll add it safely.)
        org = getattr(user, "organization", None)
        if not org:
            messages.error(request, "ADMIN user has no Organization assigned. Assign an Organization first.")
            return redirect("registry:home")

    success = False
    recent_attachments = []
    last_record = None

    if request.method == "POST":
        form = RecordCreateForm(request.POST, request.FILES, org=org, user=user)

        if form.is_valid():
            record = form.save(commit=False)

            # ✅ tenant assignment
            record.organization = org
            record.created_by = user

            if not record.owner:
                record.owner = user

            record.save()
            last_record = record

            img = form.cleaned_data.get("evidence_image")
            pdf = form.cleaned_data.get("evidence_pdf")

            if img:
                Attachment.objects.create(
                    record=record,
                    file=img,
                    file_type=AttachmentType.EVIDENCE,
                    uploaded_by=user,
                    notes="Evidence Image",
                )

            if pdf:
                Attachment.objects.create(
                    record=record,
                    file=pdf,
                    file_type=AttachmentType.CERTIFICATE_COPY,
                    uploaded_by=user,
                    notes="Evidence PDF",
                )

            recent_attachments = list(record.attachments.order_by("-created_at")[:2])

            success = True
            form = RecordCreateForm(org=org, user=user)

    else:
        form = RecordCreateForm(org=org, user=user)

    return render(
        request,
        "license-template/create.html",
        {
            "form": form,
            "success": success,
            "recent_attachments": recent_attachments,
            "last_record": last_record,
        },
    )
