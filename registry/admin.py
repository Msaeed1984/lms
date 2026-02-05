from django.contrib import admin

from .models import Record, Attachment, ActivityLog


class OrgScopedAdminMixin:
    """
    Filters queryset by the logged-in user's organization (unless superuser).
    Assumes model has `organization` field OR can be filtered via relations.
    """

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        org_id = getattr(request.user, "organization_id", None)
        if not org_id:
            return qs.none()
        # Direct org field
        if hasattr(self.model, "organization_id"):
            return qs.filter(organization_id=org_id)
        return qs


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    fields = ("file_type", "file", "version", "uploaded_by", "notes", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("uploaded_by",)


class ActivityLogInline(admin.TabularInline):
    model = ActivityLog
    extra = 0
    fields = ("action", "changed_by", "summary", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("changed_by",)


@admin.register(Record)
class RecordAdmin(OrgScopedAdminMixin, admin.ModelAdmin):
    list_display = (
        "title",
        "reference_no",
        "organization",
        "record_type",
        "category",
        "status",
        "expiry_date",
        "owner",
        "updated_at",
    )
    list_filter = ("organization", "status", "record_type", "category")
    search_fields = ("title", "reference_no", "issuing_authority", "owner__username", "owner__email")
    ordering = ("expiry_date", "title")
    date_hierarchy = "expiry_date"

    readonly_fields = ("created_at", "updated_at")

    autocomplete_fields = ("owner", "created_by")
    inlines = (AttachmentInline, ActivityLogInline)

    fieldsets = (
        ("Organization", {"fields": ("organization",)}),
        ("Record Info", {"fields": ("title", "record_type", "category", "issuing_authority", "reference_no")}),
        ("Dates & Status", {"fields": ("issue_date", "expiry_date", "status")}),
        ("Ownership", {"fields": ("owner", "department", "site_location")}),
        ("Notes", {"fields": ("notes",)}),
        ("Audit", {"fields": ("created_by", "created_at", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        # Auto-set created_by on create if not provided
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        # Safety: if non-superuser, force organization to user's org when empty
        if not request.user.is_superuser and not obj.organization_id:
            obj.organization_id = getattr(request.user, "organization_id", None)
        super().save_model(request, obj, form, change)


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("record", "file_type", "version", "uploaded_by", "created_at")
    list_filter = ("file_type",)
    search_fields = ("record__title", "record__reference_no", "uploaded_by__username", "uploaded_by__email")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("record", "uploaded_by")


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("record", "action", "changed_by", "created_at")
    list_filter = ("action",)
    search_fields = ("record__title", "record__reference_no", "changed_by__username", "summary")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("record", "changed_by")
