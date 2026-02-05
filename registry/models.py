from __future__ import annotations

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.models import Organization, TimeStampedModel


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
    record_type = models.CharField(max_length=30, choices=RecordType.choices, default=RecordType.CERTIFICATE, db_index=True)
    category = models.CharField(max_length=30, choices=RecordCategory.choices, default=RecordCategory.OTHER, db_index=True)

    issuing_authority = models.CharField(max_length=255, blank=True)
    reference_no = models.CharField(max_length=120, blank=True, db_index=True)

    issue_date = models.DateField(blank=True, null=True)
    expiry_date = models.DateField(db_index=True)

    status = models.CharField(max_length=30, choices=RecordStatus.choices, default=RecordStatus.ACTIVE, db_index=True)

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
           models.CheckConstraint(condition=models.Q(expiry_date__isnull=False), name="record_expiry_required"),

        ]
        indexes = [
            models.Index(fields=["organization", "status", "expiry_date"]),
            models.Index(fields=["organization", "category", "expiry_date"]),
            models.Index(fields=["organization", "record_type", "expiry_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.reference_no or 'N/A'})"

    def clean(self) -> None:
        # Validate date logic
        if self.issue_date and self.expiry_date and self.issue_date > self.expiry_date:
            raise ValidationError({"expiry_date": _("Expiry date must be after issue date.")})

        # Tenant-safety: if owner provided, ensure owner belongs to same organization
        if self.owner and getattr(self.owner, "organization_id", None) and self.owner.organization_id != self.organization_id:
            raise ValidationError({"owner": _("Owner must belong to the same organization.")})

        if self.created_by and getattr(self.created_by, "organization_id", None) and self.created_by.organization_id != self.organization_id:
            raise ValidationError({"created_by": _("Creator must belong to the same organization.")})

    def compute_status(self, today=None) -> str:
        """
        Compute status based on expiry date.
        'Expiring Soon' threshold is not embedded here (kept in Notifications rules),
        but we still set EXPIRED if past.
        """
        today = today or timezone.localdate()
        if self.status == RecordStatus.ARCHIVED:
            return RecordStatus.ARCHIVED
        if self.expiry_date and self.expiry_date < today:
            return RecordStatus.EXPIRED
        return self.status

    def mark_status_if_expired(self, save=True) -> bool:
        """Auto-mark expired if needed. Returns True if updated."""
        new_status = self.compute_status()
        if new_status != self.status:
            self.status = new_status
            if save:
                self.save(update_fields=["status", "updated_at"])
            return True
        return False


class AttachmentType(models.TextChoices):
    CERTIFICATE_COPY = "certificate_copy", _("Certificate Copy")
    RENEWAL_DOCUMENT = "renewal_document", _("Renewal Document")
    EVIDENCE = "evidence", _("Evidence")
    COMMUNICATION = "communication", _("Communication")
    OTHER = "other", _("Other")


def attachment_upload_to(instance: "Attachment", filename: str) -> str:
    # Organized storage: org/record/attachments/filename
    return f"org_{instance.record.organization_id}/records/{instance.record_id}/attachments/{filename}"


class Attachment(TimeStampedModel):
    """
    Attachments for a record (PDF/images).
    """
    record = models.ForeignKey(Record, on_delete=models.CASCADE, related_name="attachments", db_index=True)
    file = models.FileField(upload_to=attachment_upload_to)
    file_type = models.CharField(max_length=40, choices=AttachmentType.choices, default=AttachmentType.OTHER, db_index=True)

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
    record = models.ForeignKey(Record, on_delete=models.CASCADE, related_name="activity_logs", db_index=True)
    action = models.CharField(max_length=30, choices=ActivityAction.choices, db_index=True)

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="record_activity_logs",
        blank=True,
        null=True,
    )
    summary = models.CharField(max_length=255, blank=True)
    changes = models.JSONField(default=dict, blank=True)  # {field: {from:..., to:...}}
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["record", "action", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.record_id} {self.action} {self.created_at:%Y-%m-%d %H:%M}"
