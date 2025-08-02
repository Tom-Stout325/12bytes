from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import *



class UserRegisterForm(UserCreationForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


class PilotProfileForm(forms.ModelForm):
    class Meta:
        model = PilotProfile
        fields = ['license_number', 'license_image']
        widgets = {
            'license_date': forms.DateInput(attrs={'type': 'date'}),
            'license_image': forms.ClearableFileInput(attrs={
                'accept': '.pdf,.png,.jpg,.jpeg'
            }),
        }

    def clean_license_image(self):
        file = self.cleaned_data.get('license_image')
        if file:
            allowed_types = ['application/pdf', 'image/png', 'image/jpeg']
            if file.content_type not in allowed_types:
                raise forms.ValidationError("File type must be PDF, PNG, JPG, or JPEG.")
        return file





class TrainingForm(forms.ModelForm):
    class Meta:
        model = Training
        fields = ['title', 'date_completed', 'required', 'certificate']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'date_completed': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'certificate': forms.ClearableFileInput(attrs={
                'accept': '.pdf,.png,.jpg,.jpeg'
            }),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_certificate(self):
        file = self.cleaned_data.get('certificate')

        if file:
            allowed_types = ['application/pdf', 'image/png', 'image/jpeg']
            if file.content_type not in allowed_types:
                raise forms.ValidationError("Certificate must be a PDF, PNG, JPG, or JPEG.")
        return file
