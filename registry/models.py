from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Optional
from datetime import timedelta  # ✅ NEW

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.models import Organization, TimeStampedModel

from cloudinary.models import CloudinaryField  # ✅ Cloudinary


# =========================
# Choices
# =========================
class RecordType(models.TextChoices):
    CERTIFICATE = "certificate", _("Certificate")
    LICENSE = "license", _("License")
    PERMIT = "permit", _("Permit")
    OTHER = "other", _("Other")


class RecordCategory(models.TextChoices):
    QUALITY = "quality", _("Quality")
    HSE = "hse", _("HSE / Safety")
    ENVIRONMENT = "environment", _("Environment")
    COMPLIANCE = "compliance", _("Compliance")
    VENDOR = "vendor", _("Vendor")
    OTHER = "other", _("Other")


class RecordStatus(models.TextChoices):
    ACTIVE = "active", _("Active")
    EXPIRING_SOON = "expiring_soon", _("Expiring Soon")
    EXPIRED = "expired", _("Expired")
    RENEWED = "renewed", _("Renewed")
    ARCHIVED = "archived", _("Archived")


# =========================
# ✅ IMPORTANT FIX (for migrations)
# =========================
# Django migration 0001_initial.py references:
# registry.models.attachment_upload_to
# Even if you no longer use FileField, we must keep this function to avoid migration crash.
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(name: str) -> str:
    """
    Sanitize filename to avoid weird chars / traversal issues.
    Keeps extension.
    """
    base = Path(name).name
    base = base.replace(" ", "_")
    base = _SAFE_FILENAME_RE.sub("-", base)

    stem, ext = os.path.splitext(base)
    stem = (stem[:80] if stem else "file")
    ext = ext[:10]
    safe = f"{stem}{ext}".strip("._-")
    return safe or "file"


def attachment_upload_to(instance, filename: str) -> str:
    """
    ✅ Required by registry/migrations/0001_initial.py
    Keep stable to avoid breaking migrations.
    """
    safe = _safe_filename(filename)
    return f"lms/registry/attachments/{uuid.uuid4().hex}_{safe}"


# =========================
# Record
# =========================
class Record(TimeStampedModel):
    """
    Main entity representing a certificate/license record.
    Multi-tenant by Organization.
    """

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="records",
        db_index=True,
    )

    title = models.CharField(max_length=255, db_index=True)
    record_type = models.CharField(
        max_length=30,
        choices=RecordType.choices,
        default=RecordType.CERTIFICATE,
        db_index=True,
    )
    category = models.CharField(
        max_length=30,
        choices=RecordCategory.choices,
        default=RecordCategory.OTHER,
        db_index=True,
    )

    issuing_authority = models.CharField(max_length=255, blank=True)
    reference_no = models.CharField(max_length=120, blank=True, db_index=True)

    issue_date = models.DateField(blank=True, null=True)
    expiry_date = models.DateField(db_index=True)

    status = models.CharField(
        max_length=30,
        choices=RecordStatus.choices,
        default=RecordStatus.ACTIVE,
        db_index=True,
    )

    # Ownership / accountability
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_records",
        blank=True,
        null=True,
        db_index=True,
    )
    department = models.CharField(max_length=120, blank=True)
    site_location = models.CharField(max_length=120, blank=True)

    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_records",
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ["expiry_date", "title"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(expiry_date__isnull=False),
                name="record_expiry_required",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "status", "expiry_date"]),
            models.Index(fields=["organization", "category", "expiry_date"]),
            models.Index(fields=["organization", "record_type", "expiry_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.reference_no or 'N/A'})"

    # ---------- Safe computed helpers (for dashboard) ----------
    @property
    def days_left(self) -> Optional[int]:
        if not self.expiry_date:
            return None
        today = timezone.localdate()
        return (self.expiry_date - today).days

    @property
    def is_expired(self) -> bool:
        dl = self.days_left
        return dl is not None and dl < 0

    @property
    def is_expiring_soon(self) -> bool:
        """
        Default threshold used only for UI convenience (30 days).
        Notifications app can still use its own thresholds.
        """
        dl = self.days_left
        return dl is not None and 0 <= dl <= 30

    @property
    def computed_status(self) -> str:
        """
        Non-destructive status view:
        - If ARCHIVED keep archived
        - If expired => expired
        - If active but expiring soon => expiring_soon (display only unless you update status)
        """
        if self.status == RecordStatus.ARCHIVED:
            return RecordStatus.ARCHIVED
        if self.is_expired:
            return RecordStatus.EXPIRED
        if self.status == RecordStatus.ACTIVE and self.is_expiring_soon:
            return RecordStatus.EXPIRING_SOON
        return self.status

    def clean(self) -> None:
        # Validate date logic
        if self.issue_date and self.expiry_date and self.issue_date > self.expiry_date:
            raise ValidationError({"expiry_date": _("Expiry date must be after issue date.")})

        # Tenant-safety: if owner provided, ensure owner belongs to same organization (if user has organization_id)
        if (
            self.owner
            and getattr(self.owner, "organization_id", None)
            and self.owner.organization_id != self.organization_id
        ):
            raise ValidationError({"owner": _("Owner must belong to the same organization.")})

        if (
            self.created_by
            and getattr(self.created_by, "organization_id", None)
            and self.created_by.organization_id != self.organization_id
        ):
            raise ValidationError({"created_by": _("Creator must belong to the same organization.")})

        super().clean()

    # =========================
    # ✅ DB status logic (Admin يعتمد على DB)
    # =========================
    def compute_status_db(self, today=None, soon_days: int = 30) -> str:
        """
        Compute *database* status based on expiry_date:
        - ARCHIVED stays ARCHIVED
        - expiry_date < today => EXPIRED
        - today <= expiry_date <= today+soon_days => EXPIRING_SOON
        - expiry_date > today+soon_days => ACTIVE (or keep RENEWED if already renewed)
        """
        today = today or timezone.localdate()

        # keep archived always
        if self.status == RecordStatus.ARCHIVED:
            return RecordStatus.ARCHIVED

        if not self.expiry_date:
            return self.status

        if self.expiry_date < today:
            return RecordStatus.EXPIRED

        if self.expiry_date <= (today + timedelta(days=soon_days)):
            return RecordStatus.EXPIRING_SOON

        # if user marked it as renewed and it's still valid, keep it
        if self.status == RecordStatus.RENEWED:
            return RecordStatus.RENEWED

        return RecordStatus.ACTIVE

    def refresh_status(self, save: bool = True, soon_days: int = 30) -> bool:
        """
        Updates DB status if needed. Returns True if changed.
        Useful for admin action / scheduled job.
        """
        new_status = self.compute_status_db(soon_days=soon_days)
        if new_status != self.status:
            self.status = new_status
            if save:
                self.save(update_fields=["status", "updated_at"])
            return True
        return False

    # ---------- Existing helper (kept for backward compatibility) ----------
    def compute_status(self, today=None) -> str:
        """
        Compute status based on expiry date (legacy behavior).
        Keeps EXPIRED if past. Does not set expiring soon here (legacy).
        """
        today = today or timezone.localdate()
        if self.status == RecordStatus.ARCHIVED:
            return RecordStatus.ARCHIVED
        if self.expiry_date and self.expiry_date < today:
            return RecordStatus.EXPIRED
        return self.status

    def mark_status_if_expired(self, save: bool = True) -> bool:
        """Auto-mark expired if needed. Returns True if updated."""
        new_status = self.compute_status()
        if new_status != self.status:
            self.status = new_status
            if save:
                self.save(update_fields=["status", "updated_at"])
            return True
        return False

    def save(self, *args, **kwargs):
        """
        ✅ Auto-sync DB status on save (without breaking existing code).
        - Does NOT change ARCHIVED.
        - Keeps RENEWED if it's valid.
        """
        self.status = self.compute_status_db()
        super().save(*args, **kwargs)


# =========================
# Attachments
# =========================
class AttachmentType(models.TextChoices):
    CERTIFICATE_COPY = "certificate_copy", _("Certificate Copy")
    RENEWAL_DOCUMENT = "renewal_document", _("Renewal Document")
    EVIDENCE = "evidence", _("Evidence")
    COMMUNICATION = "communication", _("Communication")
    OTHER = "other", _("Other")


# ✅ فولدر Cloudinary (يمكن تغييره من settings)
CLOUDINARY_ATTACHMENTS_FOLDER = getattr(settings, "CLOUDINARY_ATTACHMENTS_FOLDER", "lms/attachments")


class Attachment(TimeStampedModel):
    """
    Attachments for a record (PDF/images) stored in Cloudinary.
    """

    record = models.ForeignKey(
        Record,
        on_delete=models.CASCADE,
        related_name="attachments",
        db_index=True,
    )

    # ✅ CloudinaryField بدل FileField / ImageField
    # resource_type="auto" يدعم الصور + PDF
    file = CloudinaryField(
        "file",
        folder=CLOUDINARY_ATTACHMENTS_FOLDER,
        resource_type="auto",
    )

    file_type = models.CharField(
        max_length=40,
        choices=AttachmentType.choices,
        default=AttachmentType.OTHER,
        db_index=True,
    )

    version = models.PositiveIntegerField(default=1)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_attachments",
        blank=True,
        null=True,
    )

    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["record", "file_type"]),
            models.Index(fields=["record", "version"]),
        ]

    def __str__(self) -> str:
        return f"{self.record.title} - {self.file_type} v{self.version}"

    # ---------- Helpers ----------
    def _get_file_ext(self) -> str:
        """
        Best-effort extension detection for Cloudinary resources.
        - For images: use .format
        - Otherwise: attempt original_filename
        """
        f = self.file
        if not f:
            return ""

        fmt = getattr(f, "format", None)
        if fmt:
            return f".{str(fmt).lower()}"

        original = getattr(f, "original_filename", None) or ""
        _, ext = os.path.splitext(original)
        return (ext or "").lower()

    def clean(self) -> None:
        """
        Validate attachment file types.
        Allows: pdf, jpg/jpeg/png/webp

        Note: size validation is better enforced at upload time (form/view),
        because Cloudinary uploads may happen before model clean().
        """
        super().clean()

        if not self.file:
            return

        allowed = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
        ext = self._get_file_ext()

        if ext and ext not in allowed:
            raise ValidationError(
                {"file": _(f"Unsupported file type: {ext}. Allowed: PDF, JPG, JPEG, PNG, WEBP.")}
            )

    def save(self, *args, **kwargs):
        """
        Auto-version: if adding another attachment of same type for same record,
        increment version automatically when creating new object.
        """
        if self._state.adding and self.record_id and self.file_type:
            last = (
                Attachment.objects.filter(record_id=self.record_id, file_type=self.file_type)
                .order_by("-version")
                .values_list("version", flat=True)
                .first()
            )
            if last:
                self.version = max(int(last) + 1, 1)

        super().save(*args, **kwargs)


# =========================
# Activity logs
# =========================
class ActivityAction(models.TextChoices):
    CREATED = "created", _("Created")
    UPDATED = "updated", _("Updated")
    RENEWED = "renewed", _("Renewed")
    STATUS_CHANGED = "status_changed", _("Status Changed")
    COMMENT = "comment", _("Comment")


class ActivityLog(TimeStampedModel):
    """
    Audit trail for record changes.
    Store summary + optional JSON of changes.
    """

    record = models.ForeignKey(
        Record,
        on_delete=models.CASCADE,
        related_name="activity_logs",
        db_index=True,
    )

    action = models.CharField(max_length=30, choices=ActivityAction.choices, db_index=True)

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="record_activity_logs",
        blank=True,
        null=True,
    )

    summary = models.CharField(max_length=255, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["record", "action", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.record_id} {self.action} {self.created_at:%Y-%m-%d %H:%M}"
