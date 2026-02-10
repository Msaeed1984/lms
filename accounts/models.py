from __future__ import annotations

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    """Base model: created/updated timestamps."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Organization(TimeStampedModel):
    """Tenant / Company / Department (used to isolate data per client/department)."""
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(
        max_length=30,
        unique=True,
        blank=True,
        null=True,
        validators=[RegexValidator(r"^[A-Za-z0-9\-_]+$", _("Only letters/numbers/-/_ allowed."))],
    )
    is_active = models.BooleanField(default=True, db_index=True)

    # Optional generic settings for future (JSON)
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"

    def __str__(self) -> str:
        return self.name


class UserRole(models.TextChoices):
    ADMIN = "admin", _("Admin")
    MANAGER = "manager", _("Manager")
    VIEWER = "viewer", _("Viewer")


class User(AbstractUser, TimeStampedModel):
    """
    Custom User:
    - attached to Organization
    - simple role-based authorization
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="users",
        blank=True,
        null=True,
        db_index=True,
    )
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.MANAGER,
        db_index=True,
    )

    # Notification preferences
    notify_enabled = models.BooleanField(default=True, db_index=True)
    preferred_language = models.CharField(max_length=10, default="en", blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "role"]),
            models.Index(fields=["organization", "is_active"]),
        ]
        verbose_name = "User"
        verbose_name_plural = "Users"

    # ✅ Global permission: ONLY role=ADMIN can view all organizations
    @property
    def can_view_all_orgs(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_org_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_manager(self) -> bool:
        return self.role == UserRole.MANAGER

    @property
    def is_viewer(self) -> bool:
        return self.role == UserRole.VIEWER
