from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import Record


class RecordCreateForm(forms.ModelForm):
    """
    Form for creating new Record with optional attachments.
    Evidence fields are NOT part of the model.

    ✅ Multi-tenant rules:
    - Non-ADMIN: owner dropdown shows only users within the same organization.
    - ADMIN: can view all users.
    - Always validate server-side that selected owner is allowed.
    """

    # ===== Extra upload fields =====
    evidence_image = forms.ImageField(
        required=False,
        label="Evidence Image",
    )

    evidence_pdf = forms.FileField(
        required=False,
        label="Evidence PDF",
    )

    def __init__(self, *args, org=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._org = org
        self._user = user

        User = get_user_model()

        # ✅ Owner queryset filtering
        if "owner" in self.fields:
            if user and getattr(user, "can_view_all_orgs", False):
                # ADMIN: all active users (optional: exclude users without email)
                self.fields["owner"].queryset = User.objects.filter(is_active=True).order_by("username")
            else:
                # Non-ADMIN: only same org users
                self.fields["owner"].queryset = User.objects.filter(
                    organization=org,
                    is_active=True,
                ).order_by("username")

    class Meta:
        model = Record
        fields = [
            "record_type",
            "title",
            "reference_no",
            "expiry_date",
            "owner",
        ]

        widgets = {
            "expiry_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "form-control"
                }
            ),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "reference_no": forms.TextInput(attrs={"class": "form-control"}),
            "owner": forms.Select(attrs={"class": "form-control"}),
            "record_type": forms.Select(attrs={"class": "form-control"}),
        }

    # =========================
    # Security: PDF Validation
    # =========================
    def clean_evidence_pdf(self):
        f = self.cleaned_data.get("evidence_pdf")

        if not f:
            return f

        name = (getattr(f, "name", "") or "").lower()

        # File type validation
        if not name.endswith(".pdf"):
            raise ValidationError("Only PDF files are allowed.")

        # Size validation (10MB max)
        if f.size > 10 * 1024 * 1024:
            raise ValidationError("PDF file too large (Max 10MB).")

        return f

    # =========================
    # Security: Image Validation
    # =========================
    def clean_evidence_image(self):
        f = self.cleaned_data.get("evidence_image")

        if not f:
            return f

        name = (getattr(f, "name", "") or "").lower()

        allowed = (".jpg", ".jpeg", ".png", ".webp")

        if not name.endswith(allowed):
            raise ValidationError("Only JPG, PNG, or WEBP images allowed.")

        if f.size > 10 * 1024 * 1024:
            raise ValidationError("Image too large (Max 10MB).")

        return f

    # =========================
    # Business Rule Validation
    # =========================
    def clean(self):
        cleaned_data = super().clean()

        title = cleaned_data.get("title")
        expiry = cleaned_data.get("expiry_date")
        owner = cleaned_data.get("owner")

        if not title:
            raise ValidationError("Title is required.")

        if not expiry:
            raise ValidationError("Expiry date is required.")

        # ✅ Tenant safety: prevent selecting owner from another organization (server-side)
        # Non-admin only
        if self._user and not getattr(self._user, "can_view_all_orgs", False):
            if self._org and owner and getattr(owner, "organization_id", None) != getattr(self._org, "id", None):
                raise ValidationError("Owner must belong to the same Organization.")

        return cleaned_data
