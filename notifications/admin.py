from django.contrib import admin

from .models import NotificationRule, NotificationLog


class OrgScopedAdminMixin:
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        org_id = getattr(request.user, "organization_id", None)
        if not org_id:
            return qs.none()
        return qs.filter(organization_id=org_id)


@admin.register(NotificationRule)
class NotificationRuleAdmin(OrgScopedAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "organization",
        "enabled",
        "applies_to_all",
        "record_type",
        "category",
        "channel",
        "updated_at",
    )
    list_filter = ("organization", "enabled", "applies_to_all", "record_type", "category", "channel")
    search_fields = ("name",)
    ordering = ("-enabled", "name")
    readonly_fields = ("created_at", "updated_at")

    filter_horizontal = ("escalation_recipients",)

    fieldsets = (
        ("Organization", {"fields": ("organization",)}),
        ("Rule", {"fields": ("name", "enabled", "channel")}),
        ("Scope", {"fields": ("applies_to_all", "record_type", "category")}),
        ("Reminder Schedule", {"fields": ("offsets_days",)}),
        ("Escalation", {"fields": ("escalate_enabled", "escalate_offsets_days", "escalation_recipients")}),
        ("Templates (Optional)", {"fields": ("email_subject_template", "email_body_template")}),
        ("Audit", {"fields": ("created_at", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        # Safety: if non-superuser and org not set, set it to user's org
        if not request.user.is_superuser and not obj.organization_id:
            obj.organization_id = getattr(request.user, "organization_id", None)
        super().save_model(request, obj, form, change)


@admin.register(NotificationLog)
class NotificationLogAdmin(OrgScopedAdminMixin, admin.ModelAdmin):
    list_display = (
        "record",
        "organization",
        "rule",
        "kind",
        "trigger_date",
        "status",
        "sent_at",
        "created_at",
    )
    list_filter = ("organization", "kind", "status", "trigger_date")
    search_fields = ("record__title", "record__reference_no", "payload_summary")
    ordering = ("-created_at",)
    date_hierarchy = "trigger_date"
    readonly_fields = ("created_at", "updated_at", "sent_at")

    autocomplete_fields = ("record", "rule")
