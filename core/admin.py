from django.contrib import admin

from .models import Business, BusinessFeature, BusinessMembership


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")
    ordering = ("name",)


@admin.register(BusinessMembership)
class BusinessMembershipAdmin(admin.ModelAdmin):
    list_display = ("business", "user", "role", "is_active", "joined_at")
    list_filter = ("role", "is_active")
    search_fields = ("business__name", "user__email", "user__username")


@admin.register(BusinessFeature)
class BusinessFeatureAdmin(admin.ModelAdmin):
    list_display = ("business", "feature", "enabled", "created_at")
    list_filter = ("enabled", "feature")
    search_fields = ("business__name", "feature")
