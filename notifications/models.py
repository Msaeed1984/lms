from __future__ import annotations

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.models import Organization, TimeStampedModel
from registry.models import Record, RecordCategory, RecordType


class Channel(models.TextChoices):
    EMAIL = "email", _("Email")
    TEAMS = "teams", _("Microsoft Teams (Future)")
    OTHER = "other", _("Other")


class NotificationRule(TimeStampedModel):
    """
    Defines how/when to notify.
    Example: offsets = [60, 30, 14, 7]
    Can apply globally, or per type/category.
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="notification_rules",
        db_index=True,
    )

    name = models.CharField(max_length=150, db_index=True)
    enabled = models.BooleanField(default=True, db_index=True)

    # Apply scope
    applies_to_all = models.BooleanField(default=True, db_index=True)
    record_type = models.CharField(max_length=30, choices=RecordType.choices, blank=True, null=True, db_index=True)
    category = models.CharField(max_length=30, choices=RecordCategory.choices, blank=True, null=True, db_index=True)

    # Offsets (days before expiry)
    offsets_days = models.JSONField(default=list, blank=True)  # e.g. [60, 30, 14, 7]

    # Escalation: if still not renewed near expiry
    escalate_enabled = models.BooleanField(default=True)
    escalate_offsets_days = models.JSONField(default=list, blank=True)  # e.g. [7, 1, 0]
    escalation_recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="escalation_rules",
        help_text="Users to receive escalations (e.g., managers/compliance).",
    )

    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.EMAIL)

    # Optional template fields
    email_subject_template = models.CharField(max_length=200, blank=True)
    email_body_template = models.TextField(blank=True)

    class Meta:
        ordering = ["-enabled", "name"]
        indexes = [
            models.Index(fields=["organization", "enabled"]),
            models.Index(fields=["organization", "applies_to_all"]),
            models.Index(fields=["organization", "record_type", "category"]),
        ]

    def __str__(self) -> str:
        return f"{self.organization.name} - {self.name}"

    def clean(self) -> None:
        if not isinstance(self.offsets_days, list):
            raise ValidationError({"offsets_days": _("offsets_days must be a list of integers.")})

        normalized = []
        for x in self.offsets_days:
            if not isinstance(x, int) or x < 0:
                raise ValidationError({"offsets_days": _("All offsets must be non-negative integers.")})
            normalized.append(x)

        # sort & unique
        self.offsets_days = sorted(set(normalized), reverse=True)

        if not self.applies_to_all and not (self.record_type or self.category):
            raise ValidationError(_("If applies_to_all is false, you must specify record_type and/or category."))

        if self.record_type and self.category is None and self.applies_to_all is False:
            # ok - type scope only
            pass

        if not isinstance(self.escalate_offsets_days, list):
            raise ValidationError({"escalate_offsets_days": _("escalate_offsets_days must be a list of integers.")})

        esc_norm = []
        for x in self.escalate_offsets_days:
            if not isinstance(x, int) or x < 0:
                raise ValidationError({"escalate_offsets_days": _("All escalation offsets must be non-negative integers.")})
            esc_norm.append(x)
        self.escalate_offsets_days = sorted(set(esc_norm), reverse=True)

    def matches_record(self, record: Record) -> bool:
        if record.organization_id != self.organization_id:
            return False
        if self.applies_to_all:
            return True
        if self.record_type and record.record_type != self.record_type:
            return False
        if self.category and record.category != self.category:
            return False
        return True


class NotificationKind(models.TextChoices):
    REMINDER = "reminder", _("Reminder")
    ESCALATION = "escalation", _("Escalation")


class NotificationStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    SENT = "sent", _("Sent")
    FAILED = "failed", _("Failed")
    SKIPPED = "skipped", _("Skipped")


class NotificationLog(TimeStampedModel):
    """
    Stores every notification attempt.
    Prevent duplicates using (record, rule, kind, trigger_date).
    """
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="notification_logs", db_index=True)
    record = models.ForeignKey(Record, on_delete=models.CASCADE, related_name="notification_logs", db_index=True)
    rule = models.ForeignKey(NotificationRule, on_delete=models.PROTECT, related_name="logs", db_index=True)

    kind = models.CharField(max_length=20, choices=NotificationKind.choices, default=NotificationKind.REMINDER, db_index=True)

    trigger_date = models.DateField(db_index=True, help_text="The date this notification was due to run.")
    sent_at = models.DateTimeField(blank=True, null=True)

    status = models.CharField(max_length=20, choices=NotificationStatus.choices, default=NotificationStatus.PENDING, db_index=True)
    error_message = models.TextField(blank=True)

    # Who received it (snapshot)
    recipients = models.JSONField(default=list, blank=True)  # ["email1@...", "email2@..."]
    payload_summary = models.CharField(max_length=255, blank=True)  # e.g., subject line

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["record", "rule", "kind", "trigger_date"],
                name="uniq_notification_per_record_rule_kind_triggerdate",
            )
        ]
        indexes = [
            models.Index(fields=["organization", "status", "trigger_date"]),
            models.Index(fields=["record", "kind", "trigger_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.record_id} {self.kind} {self.trigger_date} {self.status}"

    def clean(self) -> None:
        if self.organization_id != self.record.organization_id:
            raise ValidationError(_("NotificationLog organization must match record organization."))
        if self.organization_id != self.rule.organization_id:
            raise ValidationError(_("NotificationLog organization must match rule organization."))

    def mark_sent(self, recipients: list[str] | None = None, payload_summary: str = "") -> None:
        self.status = NotificationStatus.SENT
        self.sent_at = timezone.now()
        if recipients is not None:
            self.recipients = recipients
        if payload_summary:
            self.payload_summary = payload_summary

    def mark_failed(self, error: str) -> None:
        self.status = NotificationStatus.FAILED
        self.error_message = error[:5000]  # avoid huge logs
