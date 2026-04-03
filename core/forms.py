from __future__ import annotations

from django import forms

from .models import Business


class BusinessOnboardingForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Business name",
                    "autocomplete": "organization",
                }
            ),
        }
