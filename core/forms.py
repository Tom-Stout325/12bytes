from django import forms

from .models import Business


class BusinessOnboardingForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = ["name"]
