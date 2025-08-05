from django import forms
from django.forms import inlineformset_factory
from .models import *
from datetime import date
from datetime import datetime



CURRENT_YEAR = datetime.now().year
YEAR_CHOICES = [(y, y) for y in range(CURRENT_YEAR, CURRENT_YEAR - 5, -1)]

class TransForm(forms.ModelForm):
    year = forms.ChoiceField(
        choices=YEAR_CHOICES,
        initial=CURRENT_YEAR,
        label='Invoice Year',
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False,
    )
    invoice = forms.ModelChoiceField(
        queryset=Invoice.objects.none(),
        label='Invoice',
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False,
    )
    keyword = forms.ModelChoiceField(
        queryset=Keyword.objects.order_by('name'),
        label='Keyword',
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False
    )
    sub_cat = forms.ModelChoiceField(
        queryset=SubCategory.objects.all().order_by('category__category', 'sub_cat'),
        label='Sub-Category',
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False
    )

    class Meta:
        model = Transaction
        fields = (
            'year', 'invoice', 'date', 'trans_type', 'sub_cat', 'amount',
            'team', 'transaction', 'receipt', 'transport_type', 'keyword'
        )
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'transport_type': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        year = self.initial.get('year') or self.fields['year'].initial
        self.fields['invoice'].queryset = Invoice.objects.filter(date__year=year).order_by('-date')

    def clean_receipt(self):
        receipt = self.cleaned_data.get('receipt')
        if receipt and hasattr(receipt, 'content_type'):
            if receipt.content_type not in ['application/pdf', 'image/jpeg', 'image/png']:
                raise forms.ValidationError("Only PDF, JPG, or PNG files are allowed.")
        return receipt

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('sub_cat'):
            cleaned_data['category'] = cleaned_data['sub_cat'].category
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.sub_cat:
            instance.category = instance.sub_cat.category
        if commit:
            instance.save()
        return instance



class InvoiceForm(forms.ModelForm):
    year = forms.ChoiceField(
        choices=[(str(y), str(y)) for y in range(2023, datetime.now().year + 1)],
        required=False,
        label="Year",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_year'})
    )

    class Meta:
        model = Invoice
        exclude = ['amount']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'due': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'paid_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'keyword': forms.Select(attrs={'class': 'form-select'}),
            'invoice_number': forms.Select(attrs={'class': 'form-select', 'id': 'id_invoice_number'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['invoice_number'].queryset = InvoiceNumber.objects.none()

        if 'year' in self.data:
            try:
                year = int(self.data.get('year'))
                self.fields['invoice_number'].queryset = InvoiceNumber.objects.filter(race_year=year).order_by('race_order')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            year = self.instance.invoice_number.race_year
            self.fields['year'].initial = str(year)
            self.fields['invoice_number'].queryset = InvoiceNumber.objects.filter(race_year=year)


class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ['description', 'qty', 'price']
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'qty': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


InvoiceItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    extra=5,
    can_delete=True
)

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['category'] 
        widgets = {
            'category': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter category name'
            }),
        }


class SubCategoryForm(forms.ModelForm):
    class Meta:
        model = SubCategory
        fields = ['sub_cat', 'category'] 
        widgets = {
            'sub_cat': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter sub-category name'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
        }



class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['business', 'first', 'last', 'street', 'address2', 'email', 'phone']


class MileageForm(forms.ModelForm):
    class Meta:
        model = Miles
        exclude = ['user', 'total']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'begin': forms.NumberInput(attrs={'step': '0.1', 'class': 'form-control'}),
            'end': forms.NumberInput(attrs={'step': '0.1', 'class': 'form-control'}),
            'client': forms.Select(attrs={'class': 'form-control'}),
            'invoice': forms.Select(attrs={'class': 'form-control'}),  # changed from TextInput to Select
            'tax': forms.TextInput(attrs={'class': 'form-control'}),
            'job': forms.TextInput(attrs={'class': 'form-control'}),
            'vehicle': forms.TextInput(attrs={'class': 'form-control'}),
            'mileage_type': forms.Select(attrs={'class': 'form-control'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['invoice'].queryset = Invoice.objects.order_by('-date')



class MileageRateForm(forms.ModelForm):
    class Meta:
        model = MileageRate
        fields = ['rate']
        widgets = {
            'rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class KeywordForm(forms.ModelForm):
    class Meta:
        model = Keyword
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class RecurringTransactionForm(forms.ModelForm):
    class Meta:
        model = RecurringTransaction
        fields = [
            'user', 'trans_type', 'category', 'sub_cat', 'amount', 'transaction', 'day',
            'team', 'keyword', 'tax', 'receipt', 'active'
        ]
        widgets = {
            'day': forms.NumberInput(attrs={'min': 1, 'max': 28}),
        }
