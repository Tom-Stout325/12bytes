from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.auth.models import User
from datetime import timedelta, date
from decimal import Decimal
from django.conf import settings
from decimal import Decimal
from django.utils.text import slugify
from django import forms
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
try:
    from django.contrib.postgres.indexes import GinIndex
    from django.contrib.postgres.search import SearchVectorField
except ImportError:
    GinIndex = None
    SearchVectorField = None



class Category(models.Model):
    category = models.CharField(max_length=500, blank=True, null=True)
    schedule_c_line = models.CharField(max_length=10, blank=True, null=True, help_text="Enter Schedule C line number (e.g., '8', '9', '27a')")
    
    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.category or "Unnamed Category"


class SubCategory(models.Model):
    sub_cat = models.CharField(max_length=500, blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')
    slug = models.SlugField(max_length=100, unique=True, blank=True)

    class Meta:
        verbose_name_plural = "Sub Categories"
        ordering = ['sub_cat']

    def __str__(self):
        return f"{self.category} - {self.sub_cat or 'Unnamed SubCategory'}"

    def save(self, *args, **kwargs):
        if not self.slug and self.sub_cat:
            self.slug = slugify(self.sub_cat)
        super().save(*args, **kwargs)


class Keyword(models.Model):
    name       = models.CharField(max_length=500)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Team(models.Model):
    name = models.CharField(max_length=50, blank=True, null=True)
   
    def __str__(self):
        return self.name


class Client(models.Model):
    business  = models.CharField(max_length=500, blank=True, null=True)
    first     = models.CharField(max_length=500, blank=True, null=True)
    last      = models.CharField(max_length=500, blank=True, null=True)
    street    = models.CharField(max_length=500, blank=True, null=True)
    address2  = models.CharField(max_length=500, blank=True, null=True)
    email     = models.EmailField(max_length=254)
    phone     = models.CharField(max_length=500, blank=True, null=True)
    
    def __str__(self):
        return self.business
    
    
class Service(models.Model):
    service = models.CharField(max_length=500, blank=True, null=True) 
    
    def __str__(self):
        return self.service
    
    
class Transaction(models.Model):
    TRANSPORT_CHOICES = [
        ('personal_vehicle', 'Personal Vehicle'),
        ('rental_car', 'Rental Car'),
    ]
    INCOME = 'Income'
    EXPENSE = 'Expense'

    TRANS_TYPE_CHOICES = [
        (INCOME, 'Income'),
        (EXPENSE, 'Expense'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    trans_type = models.CharField(max_length=10, choices=TRANS_TYPE_CHOICES, default=EXPENSE)
    category = models.ForeignKey('Category', on_delete=models.PROTECT)
    sub_cat = models.ForeignKey('SubCategory', on_delete=models.PROTECT, null=True, blank=True)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    transaction = models.CharField(max_length=255)
    team = models.ForeignKey('Team', null=True, blank=True, on_delete=models.PROTECT)
    keyword = models.ForeignKey('Keyword', null=True, blank=True, on_delete=models.PROTECT)
    receipt = models.FileField(upload_to='receipts/', blank=True, null=True)
    date = models.DateField()
    invoice_numb = models.CharField(max_length=255, blank=True, null=True)
    invoice = models.ForeignKey('Invoice', null=True, blank=True, on_delete=models.SET_NULL, related_name='transactions')
    recurring_template = models.ForeignKey('RecurringTransaction', null=True, blank=True, on_delete=models.SET_NULL, related_name='transactions')
    transport_type = models.CharField(max_length=30, choices=TRANSPORT_CHOICES, null=True, blank=True, help_text="Used to identify if actual expenses apply")

    class Meta:
        indexes = [
            models.Index(fields=['date', 'trans_type']),
            models.Index(fields=['user', 'date']),
            models.Index(fields=['keyword']),
            models.Index(fields=['category']),
            models.Index(fields=['sub_cat']),
            models.Index(fields=['invoice_numb']),
        ]
        verbose_name_plural = "Transactions"
        ordering = ['date']
        
    @property
    def deductible_amount(self):
        if self.sub_cat and self.sub_cat.slug == 'meals':
            return round(self.amount * Decimal('0.5'), 2)
        return self.amount


    def __str__(self):
        return f"{self.transaction} - {self.amount}"
    

class Invoice(models.Model):
    invoice_number = models.OneToOneField('InvoiceNumber', on_delete=models.PROTECT, null=True, blank=True)
    invoice_numb = models.CharField(max_length=255, blank=True, null=True)
    client = models.ForeignKey('Client', on_delete=models.PROTECT)
    event = models.CharField(max_length=500, blank=True, null=True)
    location = models.CharField(max_length=500, blank=True, null=True)
    keyword = models.ForeignKey('Keyword', on_delete=models.PROTECT, default=1)
    service = models.ForeignKey('Service', on_delete=models.PROTECT)
    amount = models.DecimalField(default=0.00, max_digits=12, decimal_places=2, editable=False)
    date = models.DateField()
    due = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('Unpaid', 'Unpaid'), ('Paid', 'Paid'), ('Partial', 'Partial')],
        default='Unpaid'
    )
    search_vector = SearchVectorField(null=True, blank=True) if SearchVectorField else None

    def __str__(self):
        return f"{self.invoice_numb} - {self.keyword}"
    
    def update_amount(self):
        total = self.items.annotate(
            line_total=ExpressionWrapper(F('qty') * F('price'), output_field=DecimalField())
        ).aggregate(sum=Sum('line_total'))['sum'] or 0
        self.amount = total
        self.save()
        
    @property
    def is_paid(self):
        return self.paid_date is not None

    @property
    def days_to_pay(self):
        if self.paid_date:
            return (self.paid_date - self.date).days
        return None



class InvoiceNumber(models.Model):
    invoice_numb = models.CharField(max_length=10, unique=True)
    race_name = models.CharField(max_length=100, unique=True)
    race_order = models.IntegerField()
    race_year = models.IntegerField()

    def __str__(self):
        return f"{self.invoice_numb} - {self.race_name} ({self.race_year})"




class InvoiceItem(models.Model):
    invoice = models.ForeignKey('Invoice', on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=500) 
    qty = models.IntegerField(default=0, blank=True, null=True)
    price = models.DecimalField(max_digits=20, decimal_places=2, default=0.00, blank=True, null=True)

    def __str__(self):
        return f"{self.description} - {self.qty} x {self.price}"

    @property
    def total(self):
        return (self.qty or 0) * (self.price or 0)


class MileageRate(models.Model):
    rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.70)
    
    def __str__(self):
        return f"Current Mileage Rate: ${self.rate}"

    class Meta:
        verbose_name = "Mileage Rate"
        verbose_name_plural = "Mileage Rates"


class Miles(models.Model):
    MILEAGE_TYPE_CHOICES = [
        ('Taxable', 'Taxable'),
        ('Reimbursed', 'Reimbursed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField()
    begin = models.DecimalField(max_digits=10, decimal_places=1, null=True, validators=[MinValueValidator(0)])
    end = models.DecimalField(max_digits=10, decimal_places=1, null=True, validators=[MinValueValidator(0)])
    total = models.DecimalField(max_digits=10, decimal_places=1, null=True, editable=False)
    client = models.ForeignKey('Client', on_delete=models.PROTECT)
    invoice = models.ForeignKey('Invoice', null=True, blank=True, on_delete=models.SET_NULL)
    tax = models.CharField(max_length=10, blank=False, null=True, default="Yes")
    job = models.CharField(max_length=255, blank=True, null=True)
    vehicle = models.CharField(max_length=255, blank=False, null=True, default="Lead Foot")
    mileage_type = models.CharField(max_length=20, choices=MILEAGE_TYPE_CHOICES, default='Taxable')

    class Meta:
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['mileage_type']),
        ]
        verbose_name_plural = "Miles"
        ordering = ['-date']

    def __str__(self):
        return f"{self.invoice_numb} – {self.client} ({self.date})"


    def save(self, *args, **kwargs):
        if self.begin is not None and self.end is not None:
            self.total = round(self.end - self.begin, 1)
        else:
            self.total = None
        super().save(*args, **kwargs)



class RecurringTransaction(models.Model):
    INCOME = 'Income'
    EXPENSE = 'Expense'

    TRANS_TYPE_CHOICES = [
        (INCOME, 'Income'),
        (EXPENSE, 'Expense'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    trans_type = models.CharField(max_length=10, choices=TRANS_TYPE_CHOICES, default=EXPENSE)
    category = models.ForeignKey('Category', on_delete=models.PROTECT)
    sub_cat = models.ForeignKey('SubCategory', on_delete=models.PROTECT, null=True, blank=True)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    transaction = models.CharField(max_length=255)
    day = models.IntegerField(help_text="Day of the month to apply")
    team = models.ForeignKey(Team, null=True, on_delete=models.PROTECT, blank=True)
    keyword = models.ForeignKey('Keyword', null=True, on_delete=models.PROTECT, blank=True)
    tax = models.CharField(max_length=10, default="Yes")
    receipt = models.FileField(upload_to='receipts/', blank=True, null=True)
    account = models.CharField(max_length=255, blank=True, null=True)
    active = models.BooleanField(default=True)
    last_created = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.transaction} - {self.amount} on day {self.day}"

    class Meta:
        indexes = [models.Index(fields=['user', 'day', 'active'])]



class Receipt(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='receipts')
    date = models.DateField(blank=True, null=True)
    amount = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    keyword = models.ForeignKey('Keyword', null=True, blank=True, on_delete=models.SET_NULL)
    invoice_number = models.CharField(max_length=255, blank=True, null=True)
    receipt_file = models.FileField(upload_to='receipts/', blank=True, null=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Receipt: {self.transaction.transaction} - {self.amount or 'No Amount'}"
