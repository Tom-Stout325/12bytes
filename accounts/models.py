from __future__ import annotations

import re
from django.conf import settings
from django.db import models

from core.models import Business


class CompanyProfile(models.Model):
    business = models.OneToOneField(
        Business,
        on_delete=models.CASCADE,
        related_name="company_profile",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_company_profiles",
    )
    company_name = models.CharField(max_length=120)
    legal_name = models.CharField(max_length=120, blank=True)
    ein = models.CharField(max_length=15, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    billing_email = models.EmailField(blank=True)
    website = models.CharField(max_length=120, blank=True)
    address_line1 = models.CharField(max_length=120, blank=True)
    address_line2 = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=50, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=50, default="US")
    logo = models.ImageField(upload_to="company_logos/", blank=True, null=True)
    timezone = models.CharField(max_length=64, default="America/Indiana/Indianapolis")
    currency = models.CharField(max_length=10, default="USD")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_name"]

    def __str__(self):
        return self.company_name or f"CompanyProfile for {self.business}"

    @property
    def phone_display(self) -> str:
        p = (self.phone or "").strip()
        if p.isdigit() and len(p) == 10:
            return f"({p[:3]}) {p[3:6]}-{p[6:]}"
        return p

    @property
    def is_complete(self) -> bool:
        return bool((self.company_name or "").strip())

    def clean(self):
        super().clean()
        phone = (self.phone or "").strip()
        if phone:
            digits = re.sub(r"\D+", "", phone)
            if len(digits) == 11 and digits.startswith("1"):
                digits = digits[1:]
            if len(digits) == 10:
                self.phone = digits
