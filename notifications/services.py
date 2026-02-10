from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Optional, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import UserRole
from registry.models import Record, RecordStatus
from .models import (
    NotificationRule,
    NotificationLog,
    NotificationKind,
    NotificationStatus,
)

logger = logging.getLogger(__name__)


# =========================
# Summary
# =========================
@dataclass(frozen=True)
class EngineSummary:
    organization_id: int
    run_date: date
    created: int = 0
    sent: int = 0
    failed: int = 0
    skipped: int = 0


# =========================
# Helpers
# =========================
def _safe_emails(emails: Iterable[Optional[str]]) -> List[str]:
    out: List[str] = []
    for e in emails:
        if not e:
            continue
        e = e.strip()
        if "@" in e and len(e) <= 254:
            out.append(e)

    # unique preserve order
    seen = set()
    uniq: List[str] = []
    for e in out:
        if e not in seen:
            uniq.append(e)
            seen.add(e)
    return uniq


def _render_subject(rule: NotificationRule, record: Record, kind: str, days_left: int) -> str:
    # ✅ EMSTEEL branded default
    template = rule.email_subject_template or (
        "[EMSTEEL | Certificates & Licenses] {kind} • {title} ({ref}) • {days} day(s) left"
    )
    return (
        template.replace("{kind}", kind)
        .replace("{title}", record.title or "")
        .replace("{ref}", record.reference_no or "N/A")
        .replace("{days}", str(days_left))
        .strip()
    )


def _render_body(rule: NotificationRule, record: Record, kind: str, days_left: int) -> str:
    # ✅ EMSTEEL branded default (plain text)
    template = rule.email_body_template or (
        "Dear Team,\n\n"
        "This is an automated {kind} from EMSTEEL – IT Information Technology.\n\n"
        "Record Details:\n"
        "- Title: {title}\n"
        "- Reference No: {ref}\n"
        "- Expiry Date: {expiry}\n"
        "- Remaining: {days} day(s)\n\n"
        "Action Required:\n"
        "Please review and proceed with renewal / closure before the expiry date to maintain compliance and continuity.\n\n"
        "Regards,\n"
        "EMSTEEL – IT Information Technology\n"
        "IT Client Excellence\n"
    )
    return (
        template.replace("{kind}", kind)
        .replace("{title}", record.title or "")
        .replace("{ref}", record.reference_no or "N/A")
        .replace("{expiry}", str(record.expiry_date))
        .replace("{days}", str(days_left))
    )


def _send_email(to_emails: List[str], subject: str, body: str) -> None:
    """
    ✅ Always send using the authenticated Office365 user to avoid 'Send As' issues.
    (DEFAULT_FROM_EMAIL can still be used for display name, but must contain the same address.)
    """
    # If DEFAULT_FROM_EMAIL exists but doesn't include the actual mailbox, enforce mailbox.
    mailbox = getattr(settings, "EMAIL_HOST_USER", None) or "no-reply@example.com"
    default_from = getattr(settings, "DEFAULT_FROM_EMAIL", "") or ""
    from_email = default_from if (mailbox in default_from) else mailbox

    msg = EmailMultiAlternatives(subject=subject, body=body, from_email=from_email, to=to_emails)
    msg.send(fail_silently=False)


def _create_log_or_skip(
    record: Record,
    rule: NotificationRule,
    kind: str,
    trigger_date: date,
) -> Tuple[Optional[NotificationLog], bool]:
    """
    Create NotificationLog safely with UniqueConstraint protection.
    Returns (log, created).
    If already exists => (None, False)
    """
    try:
        with transaction.atomic():
            log = NotificationLog.objects.create(
                organization=record.organization,
                record=record,
                rule=rule,
                kind=kind,
                trigger_date=trigger_date,
                status=NotificationStatus.PENDING,
            )
            return log, True
    except IntegrityError:
        return None, False


def _get_org_managers_emails(org_id: int) -> List[str]:
    """
    ✅ Auto-pick escalation recipients from same org if not set manually:
    - role in [ADMIN, MANAGER]
    - is_active=True
    - email not empty
    """
    User = get_user_model()
    qs = (
        User.objects.filter(
            organization_id=org_id,
            role__in=[UserRole.ADMIN, UserRole.MANAGER],
            is_active=True,
        )
        .exclude(email="")
        .only("email")
    )
    return _safe_emails([u.email for u in qs])


# =========================
# Engine
# =========================
def run_notifications_for_org(org_id: int, run_date: Optional[date] = None) -> dict:
    """
    Runs notifications for one org for a given date (default: today).
    Returns dict summary.
    """
    run_date = run_date or timezone.localdate()
    _ = EngineSummary(organization_id=org_id, run_date=run_date)

    rules = (
        NotificationRule.objects.filter(organization_id=org_id, enabled=True)
        .prefetch_related("escalation_recipients")
    )

    records = (
        Record.objects.filter(organization_id=org_id)
        .exclude(status=RecordStatus.ARCHIVED)
        .select_related("owner")
    )

    created = sent = failed = skipped = 0

    for rule in rules:
        offsets = set(rule.offsets_days or [])
        esc_offsets = set(rule.escalate_offsets_days or [])

        for record in records:
            if not record.expiry_date:
                continue
            if not rule.matches_record(record):
                continue

            days_left = (record.expiry_date - run_date).days

            # =========================
            # Reminder
            # =========================
            if days_left in offsets:
                log, ok = _create_log_or_skip(record, rule, NotificationKind.REMINDER, run_date)
                if not ok:
                    skipped += 1
                else:
                    created += 1
                    try:
                        to_emails = _safe_emails([getattr(record.owner, "email", None)])
                        if not to_emails:
                            log.status = NotificationStatus.SKIPPED
                            log.error_message = "No owner email to send reminder."
                            log.save(update_fields=["status", "error_message", "updated_at"])
                            skipped += 1
                        else:
                            subject = _render_subject(rule, record, "Reminder", days_left)
                            body = _render_body(rule, record, "Reminder", days_left)
                            _send_email(to_emails, subject, body)

                            log.mark_sent(recipients=to_emails, payload_summary=subject)
                            log.save(update_fields=["status", "sent_at", "recipients", "payload_summary", "updated_at"])
                            sent += 1
                    except Exception as e:
                        logger.exception("Reminder failed org=%s record=%s rule=%s", org_id, record.id, rule.id)
                        log.mark_failed(str(e))
                        log.save(update_fields=["status", "error_message", "updated_at"])
                        failed += 1

            # =========================
            # Escalation (Managers/Admins)
            # =========================
            if rule.escalate_enabled and (days_left in esc_offsets):

                # ✅ Do not escalate if already renewed or archived
                if record.status in (RecordStatus.RENEWED, RecordStatus.ARCHIVED):
                    continue

                log, ok = _create_log_or_skip(record, rule, NotificationKind.ESCALATION, run_date)
                if not ok:
                    skipped += 1
                else:
                    created += 1
                    try:
                        # 1) manual recipients if set
                        to_emails = _safe_emails([u.email for u in rule.escalation_recipients.all()])

                        # 2) otherwise auto managers in same org
                        if not to_emails:
                            to_emails = _get_org_managers_emails(record.organization_id)

                        if not to_emails:
                            log.status = NotificationStatus.SKIPPED
                            log.error_message = "No escalation recipients configured and no org managers found."
                            log.save(update_fields=["status", "error_message", "updated_at"])
                            skipped += 1
                        else:
                            subject = _render_subject(rule, record, "Escalation", days_left)
                            body = _render_body(rule, record, "Escalation", days_left)
                            _send_email(to_emails, subject, body)

                            log.mark_sent(recipients=to_emails, payload_summary=subject)
                            log.save(update_fields=["status", "sent_at", "recipients", "payload_summary", "updated_at"])
                            sent += 1
                    except Exception as e:
                        logger.exception("Escalation failed org=%s record=%s rule=%s", org_id, record.id, rule.id)
                        log.mark_failed(str(e))
                        log.save(update_fields=["status", "error_message", "updated_at"])
                        failed += 1

    return {
        "organization_id": org_id,
        "date": str(run_date),
        "created": created,
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
    }
