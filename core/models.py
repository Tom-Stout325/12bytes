from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.text import slugify


class Business(models.Model):
    """Tenant model. Each business owns its own data."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "business"
            slug = base
            counter = 2
            while Business.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class BusinessMembership(models.Model):
    """User-to-business association with a single active business per user."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"
        VIEWER = "viewer", "Viewer"

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="business_memberships",
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(is_active=True),
                name="uniq_user_single_active_business_membership",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.business} ({self.role})"


class BusinessFeature(models.Model):
    """
    Feature switches for app/module access at the business level.

    Keep this in core so every app can share the same access model.
    """

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="features",
    )
    feature = models.CharField(max_length=50)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("business", "feature")
        ordering = ["business__name", "feature"]

    def __str__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"{self.business} - {self.feature} ({status})"


class BusinessOwnedModelMixin(models.Model):
    """Abstract mixin for business-owned records."""

    business = models.ForeignKey(Business, on_delete=models.CASCADE)

    class Meta:
        abstract = True
