from __future__ import annotations

from datetime import date
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Organization
from notifications.services import run_notifications_for_org


class Command(BaseCommand):
    help = "Run notification engine for all organizations (or a single org)."

    def add_arguments(self, parser):
        parser.add_argument("--org-id", type=int, default=None, help="Run for one Organization ID only")
        parser.add_argument("--date", type=str, default=None, help="Run date YYYY-MM-DD (default: today)")

    def handle(self, *args, **options):
        org_id = options["org_id"]
        run_date = options["date"]

        if run_date:
            y, m, d = [int(x) for x in run_date.split("-")]
            run_date_obj = date(y, m, d)
        else:
            run_date_obj = timezone.localdate()

        qs = Organization.objects.filter(is_active=True)
        if org_id:
            qs = qs.filter(id=org_id)

        total = {"created": 0, "sent": 0, "failed": 0, "skipped": 0}

        for org in qs.only("id", "name"):
            summary = run_notifications_for_org(org.id, run_date=run_date_obj)
            self.stdout.write(self.style.SUCCESS(f"{org.name}: {summary}"))
            for k in total:
                total[k] += summary[k]

        self.stdout.write(self.style.SUCCESS(f"TOTAL: {total}"))
