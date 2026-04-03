from django.contrib import admin

from .models import CompanyProfile


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = (
        "company_name",
        "business",
        "billing_email",
        "phone_display",
        "timezone",
        "currency",
        "created_at",
    )
    search_fields = (
        "company_name",
        "legal_name",
        "ein",
        "billing_email",
        "business__name",
        "created_by__email",
        "created_by__username",
    )
    list_filter = ("timezone", "currency", "country")
    readonly_fields = ("created_at", "updated_at", "phone_display")
    list_select_related = ("business", "created_by")

    fieldsets = (
        ("Business", {"fields": ("business", "created_by")}),
        ("Identity", {"fields": ("company_name", "legal_name", "ein")}),
        ("Contact", {"fields": ("phone", "phone_display", "billing_email", "website")}),
        ("Address", {"fields": ("address_line1", "address_line2", "city", "state", "postal_code", "country")}),
        ("Branding", {"fields": ("logo",)}),
        ("Locale / Formatting", {"fields": ("timezone", "currency")}),
        ("Status", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("business", "created_by")
