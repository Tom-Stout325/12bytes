from django.views.generic import TemplateView, ListView, DetailView, UpdateView, DeleteView, CreateView
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.db.models import Sum, Q, F, ExpressionWrapper, DecimalField
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.postgres.indexes import GinIndex
from django.template.loader import render_to_string
from django.db.models.functions import ExtractYear
from django.views.generic.edit import UpdateView
from django.template.loader import get_template
from django.urls import reverse_lazy, reverse
from django.templatetags.static import static
from django.core.paginator import Paginator
from django.core.mail import EmailMessage
from django.utils.timezone import now
from django.db.models import Prefetch
from django.contrib import messages
from collections import defaultdict
from datetime import datetime, date
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from calendar import monthrange, month_name
from django.views import View
from weasyprint import HTML
from pathlib import Path
import tempfile
import logging
import csv
import os
from .models import *
from .forms import *
from drones.models import Equipment
from decimal import Decimal
from django.db.models import F, ExpressionWrapper, DecimalField, Sum


logger = logging.getLogger(__name__)


class Dashboard(LoginRequiredMixin, TemplateView):
    template_name = "finance/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'dashboard'
        return context


# ---------------------------------------------------------------------------------------------------------------   Transactions


class Transactions(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = "finance/transactions.html"
    context_object_name = "transactions"
    paginate_by = 50

    def get_queryset(self):
        queryset = Transaction.objects.select_related(
            'sub_cat__category', 'sub_cat', 'team', 'keyword'
        ).filter(user=self.request.user)

        keyword_id = self.request.GET.get('keyword')
        if keyword_id and Keyword.objects.filter(id=keyword_id).exists():
            queryset = queryset.filter(keyword__id=keyword_id)

        category_id = self.request.GET.get('category')
        if category_id and Category.objects.filter(id=category_id).exists():
            queryset = queryset.filter(sub_cat__category__id=category_id)

        sub_cat_id = self.request.GET.get('sub_cat')
        if sub_cat_id and SubCategory.objects.filter(id=sub_cat_id).exists():
            queryset = queryset.filter(sub_cat__id=sub_cat_id)

        year = self.request.GET.get('year')
        if year and year.isdigit() and 1900 <= int(year) <= 9999:
            queryset = queryset.filter(date__year=year)

        # Sorting
        sort = self.request.GET.get('sort', '-date')
        valid_sort_fields = [
            'date', '-date', 'trans_type', '-trans_type',
            'transaction', '-transaction', 'keyword__name', '-keyword__name',
            'amount', '-amount', 'invoice_numb', '-invoice_numb'
        ]
        if sort not in valid_sort_fields:
            sort = '-date'

        self.current_sort = sort
        queryset = queryset.order_by(sort)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_sort'] = self.current_sort
        context['keywords'] = Keyword.objects.filter(
            id__in=Transaction.objects.filter(user=self.request.user, keyword__isnull=False)
            .values_list('keyword_id', flat=True)
        ).order_by('name')
        context['categories'] = Category.objects.filter(
            subcategories__transaction__isnull=False,
            subcategories__transaction__user=self.request.user
        ).distinct().order_by('category')
        context['subcategories'] = SubCategory.objects.filter(
            transaction__isnull=False,
            transaction__user=self.request.user
        ).distinct().order_by('sub_cat')
        context['years'] = [
            str(y) for y in Transaction.objects.filter(user=self.request.user)
            .annotate(extracted_year=ExtractYear('date'))
            .values_list('extracted_year', flat=True)
            .distinct()
            .order_by('-extracted_year')
        ]
        context['selected_keyword'] = self.request.GET.get('keyword', '')
        context['selected_category'] = self.request.GET.get('category', '')
        context['selected_sub_cat'] = self.request.GET.get('sub_cat', '')
        context['selected_year'] = self.request.GET.get('year', '')
        context['current_page'] = 'transactions'
        context['col_headers'] = [
            {'field': 'date', 'label': 'Date'},
            {'field': 'trans_type', 'label': 'Type'},
            {'field': 'transaction', 'label': 'Description'},
            {'field': 'keyword__name', 'label': 'Keyword'},
            {'field': 'amount', 'label': 'Amount'},
            {'field': 'invoice_numb', 'label': 'Invoice #'},
        ]
        return context


def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)

    context['col_headers'] = [
        {'field': 'date', 'label': 'Date'},
        {'field': 'trans_type', 'label': 'Type'},
        {'field': 'transaction', 'label': 'Description'},
        {'field': 'keyword__name', 'label': 'Keyword'},
        {'field': 'amount', 'label': 'Amount'},
        {'field': 'invoice_numb', 'label': 'Invoice #'},
    ]

    context['current_sort'] = self.request.GET.get('sort', '-date')
    context['keywords'] = Keyword.objects.filter(
        id__in=Transaction.objects.filter(user=self.request.user, keyword__isnull=False).values_list('keyword_id', flat=True)
    ).order_by('name')
    context['categories'] = Category.objects.filter(
        subcategories__transaction__isnull=False,
        subcategories__transaction__user=self.request.user
    ).distinct().order_by('category')
    context['subcategories'] = SubCategory.objects.filter(
        transaction__isnull=False, transaction__user=self.request.user
    ).distinct().order_by('sub_cat')
    context['years'] = [
        str(y) for y in Transaction.objects.filter(user=self.request.user)
        .annotate(extracted_year=ExtractYear('date'))
        .values_list('extracted_year', flat=True).distinct().order_by('-extracted_year')
        if y
    ]
    context['selected_keyword'] = self.request.GET.get('keyword', '')
    context['selected_category'] = self.request.GET.get('category', '')
    context['selected_sub_cat'] = self.request.GET.get('sub_cat', '')
    context['selected_year'] = self.request.GET.get('year', '')
    context['current_page'] = 'transactions'
    return context


class TransactionDetailView(LoginRequiredMixin, DetailView):
    model = Transaction
    template_name = 'finance/transactions_detail_view.html'
    context_object_name = 'transaction'

    def get_queryset(self):
        return Transaction.objects.select_related(
            'sub_cat__category', 'sub_cat', 'team', 'keyword'
        ).filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'transactions'
        return context


class TransactionCreateView(LoginRequiredMixin, CreateView):
    model = Transaction
    form_class = TransForm
    template_name = 'finance/transaction_add.html'
    success_url = reverse_lazy('add_transaction_success')

    def form_valid(self, form):
        form.instance.user = self.request.user

        sub_cat = form.cleaned_data.get('sub_cat')
        if sub_cat:
            form.instance.category = sub_cat.category

        try:
            with transaction.atomic():
                response = super().form_valid(form)
                messages.success(self.request, 'Transaction added successfully!')
                return response
        except Exception as e:
            logger.error(f"Error adding transaction for user {self.request.user.id}: {e}")
            messages.error(self.request, 'Error adding transaction. Please check the form.')
            return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'transactions'
        return context


class TransactionUpdateView(LoginRequiredMixin, UpdateView):
    model = Transaction
    form_class = TransForm
    template_name = 'finance/transaction_edit.html'
    success_url = reverse_lazy('transactions')

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_bound:
            logger.info("Form is bound with data: %s", request.POST)
        else:
            logger.warning("Form is NOT bound!")
        if form.is_valid():
            logger.info("Form is valid, proceeding to save.")
            return self.form_valid(form)
        else:
            logger.warning("Form is invalid with errors: %s", form.errors)
            return self.form_invalid(form)

    def form_valid(self, form):
        try:
            with transaction.atomic():
                response = super().form_valid(form)
                messages.success(self.request, 'Transaction updated successfully!')
                return response
        except Exception as e:
            logger.error(f"Error updating transaction {self.get_object().id} for user {self.request.user.id}: {e}")
            messages.error(self.request, 'Error updating transaction. Please check the form.')
            return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'transactions'

        sub_cat = self.object.sub_cat
        if sub_cat:
            context['selected_category'] = sub_cat.category
        return context


class TransactionDeleteView(LoginRequiredMixin, DeleteView):
    model = Transaction
    template_name = "finance/transaction_confirm_delete.html"
    success_url = reverse_lazy('transactions')

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                response = super().delete(request, *args, **kwargs)
                messages.success(self.request, "Transaction deleted successfully!")
                return response
        except models.ProtectedError:
            messages.error(self.request, "Cannot delete transaction due to related records.")
            return redirect('transactions')
        except Exception as e:
            logger.error(f"Error deleting transaction for user {request.user.id}: {e}")
            messages.error(self.request, "Error deleting transaction.")
            return redirect('transactions')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'transactions'
        return context


@login_required
def add_transaction_success(request):
    context = {'current_page': 'transactions'}
    return render(request, 'finance/transaction_add_success.html', context)



class Echo:
    def write(self, value):
        return value

class DownloadTransactionsCSV(LoginRequiredMixin, View):
    def get(self, request):
        try:
            # Get base queryset
            if request.GET.get('all') == 'true':
                queryset = Transaction.objects.filter(user=request.user)
            else:
                transactions_view = Transactions()
                transactions_view.request = request
                queryset = transactions_view.get_queryset()

            # Filter by year
            year = request.GET.get('year')
            if year and year.isdigit():
                queryset = queryset.filter(date__year=int(year))

            # Debug check
            if not queryset.exists():
                logger.warning(f"No transactions found for user {request.user} in export.")
                return HttpResponse("No transactions to export.", status=204)

            print("Transaction count:", queryset.count())
            logger.info(f"Transaction count for {request.user}: {queryset.count()}")

            # CSV generator
            def stream_csv(queryset):
                pseudo_buffer = Echo()
                writer = csv.writer(pseudo_buffer)
                yield writer.writerow(['Date', 'Type', 'Transaction', 'Location', 'Amount', 'Invoice #'])
                for tx in queryset.iterator():
                    yield writer.writerow([
                        tx.date,
                        tx.trans_type or '',
                        tx.transaction,
                        tx.amount,
                        tx.invoice_numb or ''
                    ])

            # Determine filename
            if request.GET.get('all') == 'true':
                filename = "all_transactions.csv"
            elif year and year.isdigit():
                filename = f"transactions_{year}.csv"
            else:
                filename = "transactions.csv"

            # Return streaming response
            response = StreamingHttpResponse(stream_csv(queryset), content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        except Exception as e:
            logger.error(f"Error generating CSV for user {request.user.id}: {e}")
            return HttpResponse("Error generating CSV", status=500)



# ---------------------------------------------------------------------------------------------------------------  Invoices


class InvoiceCreateView(LoginRequiredMixin, CreateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = 'finance/invoice_add.html'
    success_url = reverse_lazy('invoice_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.method == 'POST':
            context['formset'] = InvoiceItemFormSet(self.request.POST)
        else:
            context['formset'] = InvoiceItemFormSet()
        context['current_page'] = 'invoices'
        return context

    def form_valid(self, form):
        formset = InvoiceItemFormSet(self.request.POST)

        if formset.is_valid():
            try:
                with transaction.atomic():
                    invoice = form.save(commit=False)
                    invoice.amount = 0  # initialize to prevent errors
                    invoice.save()

                    for item_form in formset:
                        if item_form.cleaned_data and not item_form.cleaned_data.get('DELETE', False):
                            item = item_form.save(commit=False)
                            item.invoice = invoice
                            item.save()

                    # Calculate amount using the model method
                    invoice.update_amount()

                    messages.success(self.request, f"Invoice #{invoice.invoice_numb} created successfully.")
                    return redirect(self.success_url)
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                messages.error(self.request, f"Error saving invoice: {e}")
                return self.form_invalid(form)
        else:
            print("❌ Formset errors:", formset.errors)
            messages.error(self.request, "There were errors with invoice items.")
            return self.form_invalid(form)


class InvoiceUpdateView(LoginRequiredMixin, UpdateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = 'finance/invoice_update.html'
    success_url = reverse_lazy('invoice_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['formset'] = InvoiceItemFormSet(self.request.POST or None, instance=self.object)
        context['invoice'] = self.object
        context['current_page'] = 'invoices'
        return context

    def form_valid(self, form):
        formset = InvoiceItemFormSet(self.request.POST, instance=self.object)
        if formset.is_valid():
            try:
                with transaction.atomic():
                    invoice = form.save()
                    formset.save()
                    invoice.update_amount()
                    messages.success(self.request, f"Invoice #{invoice.invoice_numb} updated successfully.")
                    return super().form_valid(form)
            except Exception as e:
                messages.error(self.request, "Error updating invoice. Please check the form.")
                return self.form_invalid(form)
        else:
            messages.error(self.request, "Error in invoice items. Please check the form.")
            return self.form_invalid(form)


class InvoiceListView(LoginRequiredMixin, ListView):
    model = Invoice
    template_name = "finance/invoice_list.html"
    context_object_name = "invoices"
    paginate_by = 20

    def get_queryset(self):
        sort = self.request.GET.get('sort', 'invoice_numb')
        direction = self.request.GET.get('direction', 'desc')
        valid_sort_fields = [
            'invoice_numb', 'client__business', 'keyword__name', 'service__service',
            'amount', 'date', 'due', 'paid_date', 'days_to_pay'
        ]
        if sort not in valid_sort_fields:
            sort = 'invoice_numb'
        ordering = f"-{sort}" if direction == 'desc' else sort
        queryset = Invoice.objects.select_related('client', 'keyword', 'service').prefetch_related('items').order_by(ordering)
        search_query = self.request.GET.get('search', '')
        if search_query:
            if len(search_query) > 100:  # Prevent abuse
                search_query = search_query[:100]
            queryset = queryset.filter(
                search_vector=search_query
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['current_sort'] = self.request.GET.get('sort', 'invoice_numb')
        context['current_direction'] = self.request.GET.get('direction', 'desc')
        context['current_page'] = 'invoices'
        return context



class InvoiceDetailView(LoginRequiredMixin, DetailView):
    model = Invoice
    template_name = 'finance/invoice_detail.html'
    context_object_name = 'invoice'

    def get_queryset(self):
        return Invoice.objects.select_related('client', 'keyword', 'service').prefetch_related('items')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        logo_path = next((
            os.path.join(path, 'images/logo2.png')
            for path in (settings.STATICFILES_DIRS if hasattr(settings, 'STATICFILES_DIRS') else [])
            if os.path.exists(os.path.join(path, 'images/logo2.png'))
        ), None)
        context['logo_path'] = f'file://{logo_path}' if logo_path and os.path.exists(logo_path) else None
        context['rendering_for_pdf'] = self.request.GET.get('pdf', False)
        context['current_page'] = 'invoices'
        return context


class InvoiceDeleteView(LoginRequiredMixin, DeleteView):
    model = Invoice
    template_name = "finance/invoice_confirm_delete.html"
    success_url = reverse_lazy('invoice_list')

    def delete(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                response = super().delete(request, *args, **kwargs)
                messages.success(self.request, "Invoice deleted successfully.")
                return response
        except models.ProtectedError:
            messages.error(self.request, "Cannot delete invoice due to related records.")
            return redirect('invoice_list')
        except Exception as e:
            logger.error(f"Error deleting invoice for user {request.user.id}: {e}")
            messages.error(self.request, "Error deleting invoice.")
            return redirect('invoice_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'invoices'
        return context
    

@login_required
def invoice_review(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    transactions = Transaction.objects.filter(invoice=invoice).select_related('sub_cat', 'category')
    mileage_entries = Miles.objects.filter(
        invoice=invoice,
        user=request.user,
        tax__iexact="Yes",
        mileage_type="Taxable"
    )

    try:
        rate = MileageRate.objects.first().rate if MileageRate.objects.exists() else Decimal("0.70")
    except Exception as e:
        logger.error(f"Error fetching mileage rate: {e}")
        rate = Decimal("0.70")

    total_mileage_miles = mileage_entries.aggregate(Sum('total'))['total__sum'] or 0
    mileage_dollars = round(total_mileage_miles * rate, 2)

    total_expenses = Decimal("0.00")
    deductible_expenses = Decimal("0.00")
    total_income = Decimal("0.00")

    for t in transactions:
        if t.trans_type == 'Income':
            total_income += t.amount
        elif t.trans_type == 'Expense':
            total_expenses += t.amount

            is_meal = t.sub_cat and t.sub_cat.slug == 'meals'
            is_fuel = t.sub_cat and t.sub_cat.slug == 'fuel'
            is_personal = t.transport_type == "personal_vehicle"

            if is_meal:
                deductible_expenses += t.deductible_amount
            elif is_fuel and is_personal:
                pass  # Not deductible, but included in net income
            else:
                deductible_expenses += t.amount

    net_income = total_income - total_expenses
    taxable_income = total_income - deductible_expenses - mileage_dollars

    context = {
        'invoice': invoice,
        'transactions': transactions,
        'mileage_entries': mileage_entries,
        'mileage_rate': rate,
        'mileage_dollars': mileage_dollars,
        'invoice_amount': invoice.amount,
        'total_expenses': total_expenses,
        'deductible_expenses': deductible_expenses,
        'total_income': total_income,
        'net_income': net_income,
        'taxable_income': taxable_income,
        'now': now(),
        'current_page': 'invoices',
    }

    return render(request, 'finance/invoice_review.html', context)


@login_required
def invoice_review_pdf(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)

    transactions = Transaction.objects.filter(invoice=invoice, user=request.user).select_related('sub_cat', 'category')

    mileage_entries = Miles.objects.filter(
        invoice=invoice,
        user=request.user,
        tax__iexact="Yes",
        mileage_type="Taxable"
    )

    try:
        rate = MileageRate.objects.first().rate if MileageRate.objects.exists() else Decimal("0.70")
    except Exception as e:
        logger.error(f"Error fetching mileage rate: {e}")
        rate = Decimal("0.70")

    total_mileage_miles = mileage_entries.aggregate(Sum('total'))['total__sum'] or 0
    mileage_dollars = (Decimal(str(total_mileage_miles)) * Decimal(str(rate))).quantize(Decimal('0.01'))

    total_expenses = Decimal('0.00')
    deductible_expenses = Decimal('0.00')
    total_income = Decimal('0.00')

    for t in transactions:
        if t.trans_type == 'Income':
            total_income += t.amount
        elif t.trans_type == 'Expense':
            total_expenses += t.amount
            is_meal = t.sub_cat and t.sub_cat.id == 26
            is_gas = t.sub_cat and t.sub_cat.id == 27
            is_personal_vehicle = t.transport_type == 'personal_vehicle'

            if is_meal:
                deductible_expenses += t.deductible_amount
            elif is_gas and is_personal_vehicle:
                continue
            else:
                deductible_expenses += t.amount

    net_income = total_income - total_expenses
    taxable_income = total_income - deductible_expenses - mileage_dollars

    context = {
        'invoice': invoice,
        'transactions': transactions,
        'mileage_entries': mileage_entries,
        'mileage_rate': rate,
        'mileage_dollars': mileage_dollars,
        'invoice_amount': invoice.amount,
        'total_expenses': total_expenses,
        'deductible_expenses': deductible_expenses,
        'total_income': total_income,
        'net_income': net_income,
        'taxable_income': taxable_income,
        'now': now(),
        'current_page': 'invoices',
    }

    try:
        template = get_template('finance/invoice_review_pdf.html')
        html_string = template.render(context)
        html_string = "<style>@page { size: 8.5in 11in; margin: 1in; }</style>" + html_string

        if request.GET.get("preview") == "1":
            return HttpResponse(html_string)

        with tempfile.NamedTemporaryFile(delete=True) as tmp:
            HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(tmp.name)
            tmp.seek(0)
            response = HttpResponse(tmp.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_numb}.pdf"'
            return response
    except Exception as e:
        logger.error(f"Error generating PDF for invoice {pk} by user {request.user.id}: {e}")
        messages.error(request, "Error generating PDF.")
        return redirect('invoice_detail', pk=pk)


    
@login_required
def unpaid_invoices(request):
    invoices = Invoice.objects.filter(paid__iexact="No").select_related('client').order_by('due_date')
    context = {'invoices': invoices, 'current_page': 'invoices'}
    return render(request, 'finance/unpaid_invoices.html', context)


@login_required
def export_invoices_csv(request):
    invoice_view = InvoiceListView()
    invoice_view.request = request
    queryset = invoice_view.get_queryset()

    class Echo:
        def write(self, value):
            return value

    def stream_csv(queryset):
        writer = csv.writer(Echo())
        yield writer.writerow(['Invoice #', 'Client', 'Location', 'Service', 'Amount', 'Date', 'Due', 'Paid', 'Days to Pay'])
        for invoice in queryset.iterator():
            yield writer.writerow([
                invoice.invoice_numb,
                str(invoice.client),
                invoice.keyword.name if invoice.keyword else '',
                str(invoice.service),
                invoice.amount,
                invoice.date,
                invoice.due,
                invoice.paid_date or "No",
                invoice.days_to_pay if invoice.paid_date else "—"
            ])

    try:
        response = StreamingHttpResponse(stream_csv(queryset), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="invoices.csv"'
        return response
    except Exception as e:
        logger.error(f"Error generating CSV for user {request.user.id}: {e}")
        return HttpResponse("Error generating CSV", status=500)


@login_required
def export_invoices_pdf(request):
    invoice_view = InvoiceListView()
    invoice_view.request = request
    invoices = invoice_view.get_queryset()[:1000]

    if not invoices.exists():
        messages.error(request, "No invoices to export.")
        return redirect('invoice_list')

    try:
        template = get_template('finance/invoice_pdf_export.html')
        html_string = template.render({'invoices': invoices, 'current_page': 'invoices'})
        with tempfile.NamedTemporaryFile(delete=True) as output:
            HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(output.name)
            output.seek(0)
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="invoices.pdf"'
            response.write(output.read())
            return response
    except Exception as e:
        logger.error(f"Error generating PDF for user {request.user.id}: {e}")
        messages.error(request, "Error generating PDF.")
        return redirect('invoice_list')
    


# ---------------------------------------------------------------------------------------------------------------  Categories


class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'finance/category_page.html'
    context_object_name = 'category'

    def get_queryset(self):
        return Category.objects.prefetch_related('subcategories').order_by('category')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'categories'
        return context


class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "finance/category_form.html"
    success_url = reverse_lazy('category_page')

    def form_valid(self, form):
        messages.success(self.request, "Category added successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'categories'
        return context


class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "finance/category_form.html"
    success_url = reverse_lazy('category_page')

    def form_valid(self, form):
        messages.success(self.request, "Category updated successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'categories'
        return context


class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = Category
    template_name = "finance/category_confirm_delete.html"
    success_url = reverse_lazy('category_page')

    def delete(self, request, *args, **kwargs):
        try:
            response = super().delete(request, *args, **kwargs)
            messages.success(self.request, "Category deleted successfully!")
            return response
        except models.ProtectedError:
            messages.error(self.request, "Cannot delete category due to related transactions.")
            return redirect('category_page')
        except Exception as e:
            logger.error(f"Error deleting category for user {request.user.id}: {e}")
            messages.error(self.request, "Error deleting category.")
            return redirect('category_page')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'categories'
        return context


@login_required
def category_summary(request):
    year = request.GET.get('year')
    context = get_summary_data(request, year)
    context['available_years'] = [d.year for d in Transaction.objects.filter(
        user=request.user).dates('date', 'year', order='DESC').distinct()]
    context['current_page'] = 'reports'
    return render(request, 'finance/category_summary.html', context)


@login_required
def category_summary_pdf(request):
    year = request.GET.get('year')
    context = get_summary_data(request, year)
    context['now'] = timezone.now()
    context['selected_year'] = year or timezone.now().year
    context['logo_url'] = request.build_absolute_uri('/static/img/logo.png')

    try:
        template = get_template('finance/category_summary_pdf.html')
        html_string = template.render(context)
        html_string = "<style>@page { size: 8.5in 11in; margin: 1in; }</style>" + html_string

        if request.GET.get("preview") == "1":
            return HttpResponse(html_string)

        with tempfile.NamedTemporaryFile(delete=True) as tmp:
            HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(tmp.name)
            tmp.seek(0)
            response = HttpResponse(tmp.read(), content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename=\"category_summary.pdf\"'
            return response
    except Exception as e:
        logger.error(f"Error generating category summary PDF: {e}")
        messages.error(request, "Error generating PDF.")
        return redirect('category_summary')


# ---------------------------------------------------------------------------------------------------------------   Sub-Categories


class SubCategoryCreateView(LoginRequiredMixin, CreateView):
    model = SubCategory
    form_class = SubCategoryForm
    template_name = "finance/sub_category_form.html"
    success_url = reverse_lazy('category_page')

    def form_valid(self, form):
        messages.success(self.request, "Sub-Category added successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'categories'
        return context


class SubCategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = SubCategory
    form_class = SubCategoryForm
    template_name = "finance/sub_category_form.html"
    success_url = reverse_lazy('category_page')
    context_object_name = "sub_cat"

    def form_valid(self, form):
        messages.success(self.request, "Sub-Category updated successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'categories'
        return context


class SubCategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = SubCategory
    template_name = "finance/sub_category_confirm_delete.html"
    success_url = reverse_lazy('category_page')

    def delete(self, request, *args, **kwargs):
        try:
            response = super().delete(request, *args, **kwargs)
            messages.success(self.request, "Sub-Category deleted successfully!")
            return response
        except models.ProtectedError:
            messages.error(self.request, "Cannot delete sub-category due to related transactions.")
            return redirect('category_page')
        except Exception as e:
            logger.error(f"Error deleting sub-category for user {request.user.id}: {e}")
            messages.error(self.request, "Error deleting sub-category.")
            return redirect('category_page')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'categories'
        return context


# ---------------------------------------------------------------------------------------------------------------  Clients


class ClientListView(LoginRequiredMixin, ListView):
    model = Client
    template_name = "finance/client_list.html"
    context_object_name = "clients"
    ordering = ['business']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'clients'
        return context


class ClientCreateView(LoginRequiredMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = "finance/client_form.html"
    success_url = reverse_lazy('client_list')

    def form_valid(self, form):
        messages.success(self.request, "Client added successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'clients'
        return context


class ClientUpdateView(LoginRequiredMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = "finance/client_form.html"
    success_url = reverse_lazy('client_list')

    def form_valid(self, form):
        messages.success(self.request, "Client updated successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'clients'
        return context


class ClientDeleteView(LoginRequiredMixin, DeleteView):
    model = Client
    template_name = "finance/client_confirm_delete.html"
    success_url = reverse_lazy('client_list')

    def delete(self, request, *args, **kwargs):
        try:
            response = super().delete(request, *args, **kwargs)
            messages.success(self.request, "Client deleted successfully!")
            return response
        except models.ProtectedError:
            messages.error(self.request, "Cannot delete client due to related invoices.")
            return redirect('client_list')
        except Exception as e:
            logger.error(f"Error deleting client for user {request.user.id}: {e}")
            messages.error(self.request, "Error deleting client.")
            return redirect('client_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'clients'
        return context


# --------------------------------------------------------------------------------------------------------------- Financial Reports


def get_summary_data(request, year):
    EXCLUDED_INCOME_CATEGORIES = ['Equipment Sale']

    try:
        current_year = timezone.now().year
        selected_year = int(year) if year and str(year).isdigit() else current_year
    except ValueError:
        messages.error(request, "Invalid year selected.")
        selected_year = current_year

    transactions = Transaction.objects.filter(
        user=request.user,
        date__year=selected_year
    ).select_related('sub_cat__category')

    income_data = defaultdict(lambda: {
        'total': Decimal('0.00'),
        'subcategories': defaultdict(lambda: [Decimal('0.00'), None])
    })

    expense_data = defaultdict(lambda: {
        'total': Decimal('0.00'),
        'subcategories': defaultdict(lambda: [Decimal('0.00'), None])
    })

    for t in transactions:
        category = t.sub_cat.category if t.sub_cat and t.sub_cat.category else None
        sub_cat_name = t.sub_cat.sub_cat if t.sub_cat else "Uncategorized"
        cat_name = category.category if category else "Uncategorized"
        sched_line = category.schedule_c_line if category and category.schedule_c_line else None

        is_meals = t.sub_cat and t.sub_cat.slug == 'meals'
        is_fuel = t.sub_cat and t.sub_cat.slug == 'fuel'
        is_personal_vehicle = t.transport_type == "personal_vehicle"

        if is_meals:
            amount = round(t.amount * Decimal('0.5'), 2)
        elif is_fuel and is_personal_vehicle:
            amount = Decimal('0.00')
        else:
            amount = t.amount

        if t.trans_type == 'Income':
            if cat_name in EXCLUDED_INCOME_CATEGORIES:
                continue
            target_data = income_data
        else:
            target_data = expense_data

        target_data[cat_name]['total'] += amount
        target_data[cat_name]['subcategories'][sub_cat_name][0] += amount
        target_data[cat_name]['subcategories'][sub_cat_name][1] = sched_line

    def format_data(data_dict):
        return [
            {
                'category': cat,
                'total': values['total'],
                'subcategories': [(sub, amt_sched[0], amt_sched[1]) for sub, amt_sched in values['subcategories'].items()]
            }
            for cat, values in sorted(data_dict.items())
        ]

    income_category_totals = format_data(income_data)
    expense_category_totals = format_data(expense_data)

    income_total = sum(item['total'] for item in income_category_totals)
    expense_total = sum(item['total'] for item in expense_category_totals)
    net_profit = income_total - expense_total

    available_years = Transaction.objects.filter(user=request.user).dates('date', 'year', order='DESC')

    return {
        'selected_year': selected_year,
        'income_category_totals': income_category_totals,
        'expense_category_totals': expense_category_totals,
        'income_category_total': income_total,
        'expense_category_total': expense_total,
        'net_profit': net_profit,
        'available_years': [d.year for d in available_years],
    }



@login_required
def financial_statement(request):
    year = request.GET.get('year', str(timezone.now().year))
    context = get_summary_data(request, year)
    context['current_page'] = 'reports'
    return render(request, 'finance/financial_statement.html', context)


@login_required
def financial_statement_pdf(request, year):
    try:
        selected_year = int(year)
    except ValueError:
        selected_year = timezone.now().year

    context = get_summary_data(request, selected_year)
    context['now'] = timezone.now()

    html_string = render_to_string('finance/financial_statement_pdf.html', context)
    pdf = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Financial_Statement_{selected_year}.pdf"'

    return response


def get_schedule_c_summary(transactions):
    line_summary = defaultdict(lambda: {'total': Decimal('0.00'), 'items': set()})

    for t in transactions:
        if not t.sub_cat or not t.sub_cat.category or not t.sub_cat.category.schedule_c_line:
            continue
        line = t.sub_cat.category.schedule_c_line
        amount = t.amount
        if t.trans_type == 'Expense':
            if t.sub_cat_id == 26:  # meals (50%)
                amount *= Decimal('0.5')
            elif t.sub_cat_id == 27 and t.transport_type == 'personal_vehicle':
                continue  # skip personal fuel
            amount = -abs(amount)
        line_summary[line]['total'] += amount
        line_summary[line]['items'].add(t.sub_cat.category.category)

    return [
        {'line': line, 'total': data['total'], 'categories': sorted(data['items'])}
        for line, data in sorted(line_summary.items())
    ]

    
    
@login_required
def schedule_c_summary(request):
    year = request.GET.get('year', timezone.now().year)
    transactions = Transaction.objects.filter(user=request.user, date__year=year).select_related('sub_cat__category')
    summary = get_schedule_c_summary(transactions)

    income_total = sum(t.amount for t in transactions if t.trans_type == 'Income')
    total_expenses = sum(row['total'] for row in summary if row['total'] < 0)
    net_profit = income_total + total_expenses

    return render(request, 'finance/schedule_c_summary.html', {
        'summary': summary,
        'income_total': income_total,
        'net_profit': net_profit,
        'selected_year': year,
        'current_page': 'reports',
    })



@login_required
def schedule_c_summary_pdf(request, year):
    transactions = Transaction.objects.filter(user=request.user, date__year=year).select_related('sub_cat__category')
    summary = get_schedule_c_summary(transactions)
    income_total = sum(t.amount for t in transactions if t.trans_type == 'Income')
    total_expenses = sum(row['total'] for row in summary if row['total'] < 0)
    net_profit = income_total + total_expenses

    logo_url = request.build_absolute_uri(static('images/logo2.png'))

    html = render_to_string('finance/schedule_c_summary_pdf.html', {
        'summary': summary,
        'income_total': income_total,
        'net_profit': net_profit,
        'selected_year': year,
        'logo_url': logo_url,
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename=schedule_c_summary_{year}.pdf'
    HTML(string=html).write_pdf(response)
    return response


@login_required
def form_4797_view(request):
    sold_equipment = Equipment.objects.filter(date_sold__isnull=False, sale_price__isnull=False)
    report_data = []

    for item in sold_equipment:
        purchase_cost = Decimal('0.00') if item.deducted_full_cost else (item.purchase_price or Decimal('0.00'))
        gain = item.sale_price - item.purchase_cost

        report_data.append({
            'name': item.name,
            'date_sold': item.date_sold,
            'sale_price': item.sale_price,
            'purchase_cost': item.purchase_cost,
            'gain': gain,
        })

    context = {
        'report_data': report_data,
        'current_page': 'form_4797'
    }
    return render(request, 'finance/form_4797.html', context)



@login_required
def form_4797_pdf(request):
    sold_equipment = Equipment.objects.filter(date_sold__isnull=False, sale_price__isnull=False)
    report_data = []

    for item in sold_equipment:
        basis = Decimal('0.00') if item.deducted_full_cost else (item.purchase_price or Decimal('0.00'))
        gain = item.sale_price - basis

        report_data.append({
            'name': item.name,
            'date_sold': item.date_sold,
            'sale_price': item.sale_price,
            'basis': basis,
            'gain': gain,
        })

    context = {
        'report_data': report_data,
        'company_name': "Airborne Images",
 
    }

    template = get_template('finance/form_4797_pdf.html')
    html_string = template.render(context)

    with tempfile.NamedTemporaryFile(delete=True, suffix=".pdf") as output:
        HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(output.name)
        output.seek(0)
        pdf = output.read()

    preview = request.GET.get('preview') == '1'
    disposition = 'inline' if preview else 'attachment'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'{disposition}; filename="form_4797.pdf"'
    return response


@login_required
def nhra_summary(request):
    current_year = timezone.now().year
    years = [current_year, current_year - 1, current_year - 2]
    excluded_ids = [35, 133, 34, 67, 100]

    summary_data = Transaction.objects.filter(
        user=request.user
    ).exclude(keyword__id__in=excluded_ids).filter(
        date__year__in=years, trans_type__isnull=False
    ).values('keyword__name', 'date__year', 'trans_type').annotate(
        total=Sum('amount')
    ).order_by('keyword__name', 'date__year')

    result = defaultdict(lambda: {y: {"income": 0, "expense": 0, "net": 0} for y in years})
    
    for item in summary_data:
        keyword = item['keyword__name']
        year = item['date__year']
        trans_type = item['trans_type'].lower()
        if keyword:
            result[keyword][year][trans_type] = item['total']
            result[keyword][year]['net'] = result[keyword][year]['income'] - result[keyword][year]['expense']

    result_dict = dict(result)

    logger.debug(f"NHRA summary data for user {request.user.id}: {result_dict}")

    context = {
        "years": years,
        "summary_data": result_dict,
        "urls": {
            "reports": "/finance/finance/"
        },
        'current_page': 'reports'
    }
    return render(request, "nhra/nhra_summary.html", context)



@login_required
def race_expense_report(request):
    current_year = now().year
    years = [current_year, current_year - 1, current_year - 2]

    travel_subcategories = [
        'Travel: Car Rental',
        'Travel: Flights',
        'Travel: Fuel',
        'Travel: Hotel',
        'Travel: Meals',
        'Travel: Miscellaneous'
    ]

    selected_keyword = request.GET.get('keyword', '')

    base_qs = Transaction.objects.filter(
        user=request.user,
        trans_type='Expense',
        sub_cat__sub_cat__in=travel_subcategories,
        date__year__in=years
    ).select_related('keyword', 'sub_cat')

    # Get list of all keywords used in filtered transactions
    all_keywords = base_qs.values_list('keyword__name', flat=True).distinct().order_by('keyword__name')

    if selected_keyword:
        base_qs = base_qs.filter(keyword__name=selected_keyword)

    summary_data = base_qs.values(
        'keyword__name', 'sub_cat__sub_cat', 'date__year'
    ).annotate(total=Sum('amount')).order_by('sub_cat__sub_cat', 'date__year')

    result = defaultdict(lambda: defaultdict(lambda: {y: 0 for y in years}))
    keyword_totals = defaultdict(lambda: {y: 0 for y in years})
    yearly_totals = {y: 0 for y in years}

    for item in summary_data:
        keyword = item['keyword__name'] or 'Unspecified'
        subcategory = item['sub_cat__sub_cat']
        year = item['date__year']
        amount = item['total']
        result[keyword][subcategory][year] = amount
        keyword_totals[keyword][year] += amount
        yearly_totals[year] += amount

    context = {
        'years': years,
        'keywords': all_keywords,
        'selected_keyword': selected_keyword,
        'summary_data': dict(result),
        'keyword_totals': dict(keyword_totals),
        'yearly_totals': yearly_totals,
        'travel_subcategories': travel_subcategories,
        'current_page': 'reports',
    }

    return render(request, 'race_expense_report.html', context)


@login_required
def travel_expense_analysis(request):
    current_year = now().year
    available_years = list(range(2023, current_year + 1))

    selected_year = int(request.GET.get('year', current_year))

    income_subcat_id = 19  # Services: Drone
    expense_subcat_ids = [100, 23, 24, 27, 25, 26, 28]

    income_total = Transaction.objects.filter(
        user=request.user,
        date__year=selected_year,
        trans_type='Income',
        sub_cat_id=income_subcat_id
    ).aggregate(total=Sum('amount'))['total'] or 0

    expenses_qs = Transaction.objects.filter(
        user=request.user,
        date__year=selected_year,
        trans_type='Expense',
        sub_cat_id__in=expense_subcat_ids
    ).values('sub_cat__sub_cat', 'sub_cat_id') \
     .annotate(total=Sum('amount')).order_by('sub_cat__sub_cat')

    expense_data = []
    total_expense = sum(row['total'] for row in expenses_qs)

    for row in expenses_qs:
        amount = row['total']
        percentage = (amount / total_expense) * 100 if total_expense else 0
        expense_data.append({
            'name': row['sub_cat__sub_cat'],
            'amount': amount,
            'percentage': round(percentage, 2)
        })

    context = {
        'selected_year': selected_year,
        'available_years': available_years,
        'income_total': income_total,
        'expense_data': expense_data,
        'total_expense': total_expense,
        'current_page': 'reports',
    }

    return render(request, 'nhra/travel_expense_analysis.html', context)



@login_required
def travel_expense_analysis_pdf(request):
    selected_year = int(request.GET.get('year', now().year))

    income_subcat_id = 19
    expense_subcat_ids = [100, 23, 24, 27, 25, 26, 28]

    income_total = Transaction.objects.filter(
        user=request.user,
        date__year=selected_year,
        trans_type='Income',
        sub_cat_id=income_subcat_id
    ).aggregate(total=Sum('amount'))['total'] or 0

    expenses_qs = Transaction.objects.filter(
        user=request.user,
        date__year=selected_year,
        trans_type='Expense',
        sub_cat_id__in=expense_subcat_ids
    ).values('sub_cat__sub_cat', 'sub_cat_id') \
     .annotate(total=Sum('amount')).order_by('sub_cat__sub_cat')

    expense_data = []
    total_expense = sum(row['total'] for row in expenses_qs)

    for row in expenses_qs:
        amount = row['total']
        percentage = (amount / total_expense) * 100 if total_expense else 0
        expense_data.append({
            'name': row['sub_cat__sub_cat'],
            'amount': amount,
            'percentage': round(percentage, 2)
        })

    html_string = render_to_string('finance/travel_expense_analysis_pdf.html', {
        'selected_year': selected_year,
        'income_total': income_total,
        'expense_data': expense_data,
        'total_expense': total_expense,
    })

    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    pdf_file = html.write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'filename="Travel_Expense_Report_{selected_year}.pdf"'
    return response


@login_required
def race_expense_report_pdf(request):
    current_year = now().year
    years = [current_year, current_year - 1, current_year - 2]
    travel_subcategories = [
        'Travel: Car Rental', 'Travel: Flights', 'Travel: Fuel',
        'Travel: Hotel', 'Travel: Meals', 'Travel: Miscellaneous'
    ]
    transactions = Transaction.objects.filter(
        user=request.user,
        trans_type='Expense',
        sub_cat__sub_cat__in=travel_subcategories,
        date__year__in=years
    ).select_related('keyword', 'sub_cat')
    summary_data = transactions.values(
        'keyword__name', 'sub_cat__sub_cat', 'date__year'
    ).annotate(total=Sum('amount')).order_by('keyword__name', 'sub_cat__sub_cat', 'date__year')
    result = defaultdict(lambda: defaultdict(lambda: {y: 0 for y in years}))
    for item in summary_data:
        keyword = item['keyword__name'] or 'Unspecified'
        subcategory = item['sub_cat__sub_cat']
        year = item['date__year']
        result[keyword][subcategory][year] = item['total']
    keyword_totals = defaultdict(lambda: {y: 0 for y in years})
    yearly_totals = {y: 0 for y in years}
    for keyword, subcats in result.items():
        for subcat, year_data in subcats.items():
            for year, amount in year_data.items():
                keyword_totals[keyword][year] += amount
                yearly_totals[year] += amount
    context = {
        'years': years,
        'summary_data': dict(result),
        'keyword_totals': dict(keyword_totals),
        'yearly_totals': yearly_totals,
        'travel_subcategories': travel_subcategories,
        'current_page': 'reports'
    }
    try:
        template = get_template('finance/race_expense_report.html')
        html_string = template.render(context)
        html_string = "<style>@page { size: 8.5in 11in; margin: 1in; }</style>" + html_string
        with tempfile.NamedTemporaryFile(delete=True) as output:
            HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(output.name)
            output.seek(0)
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="race_expense_report.pdf"'
            response.write(output.read())
        return response
    except Exception as e:
        logger.error(f"Error generating PDF for user {request.user.id}: {e}")
        messages.error(request, "Error generating PDF.")
        return redirect('race_expense_report')



@login_required
def reports_page(request):
    context = {'current_page': 'reports'}
    return render(request, 'finance/reports.html', context)


# ---------------------------------------------------------------------------------------------------------------   Emails


@require_POST
def send_invoice_email(request, invoice_id):
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    try:
        # Generate invoice HTML and PDF
        html_string = render_to_string('finance/invoice_detail.html', {
            'invoice': invoice,
            'current_page': 'invoices'
        })
        html = HTML(string=html_string, base_url=request.build_absolute_uri())
        pdf_file = html.write_pdf()

        # Email content
        subject = f"Invoice #{invoice.invoice_numb} from Airborne Images"
        body = f"""
        Hi {invoice.client.first},<br><br>
        Attached is your invoice for the event: <strong>{invoice.event}</strong>.<br><br>
        Let me know if you have any questions!<br><br>
        Thank you!,<br>
        <strong>Tom Stout</strong><br>
        Airborne Images<br>
        <a href="http://www.airborneimages.com" target="_blank">www.AirborneImages.com</a><br>
        "Views From Above!"<br>
        """

        from_email = "tom@tom-stout.com"
        recipient = [invoice.client.email or getattr(settings, 'DEFAULT_EMAIL', None)]
        if not recipient[0]:
            raise ValueError("No valid email address provided.")

        # Construct and send email with BCC
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email,
            to=recipient,
            bcc=["tom@tom-stout.com"]
        )
        email.content_subtype = 'html'
        email.attach(f"Invoice_{invoice.invoice_numb}.pdf", pdf_file, "application/pdf")
        email.send()

        return JsonResponse({'status': 'success', 'message': 'Invoice emailed successfully!'})
    except Exception as e:
        logger.error(f"Error sending email for invoice {invoice_id} by user {request.user.id}: {e}")
        return JsonResponse({'status': 'error', 'message': 'Failed to send email'}, status=500)

# ---------------------------------------------------------------------------------------------------------------  Mileage


def get_mileage_context(request):
    try:
        rate = MileageRate.objects.first().rate if MileageRate.objects.exists() else 0.70
    except Exception as e:
        logger.error(f"Error fetching mileage rate: {e}")
        rate = 0.70
        messages.error(request, "Error fetching mileage rate. Using default rate.")

    year = datetime.now().year
    entries = Miles.objects.filter(user=request.user, date__year=year)
    paginator = Paginator(entries, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    taxable = entries.filter(mileage_type='Taxable')
    total_miles = taxable.aggregate(Sum('total'))['total__sum'] or 0

    return {
        'mileage_list': page_obj,
        'page_obj': page_obj,
        'total_miles': total_miles,
        'taxable_dollars': total_miles * Decimal(str(rate)),
        'current_year': year,
        'mileage_rate': rate,
        'current_page': 'mileage'
    }


@login_required
def mileage_log(request):
    context = get_mileage_context(request)
    return render(request, 'finance/mileage_log.html', context)


class MileageCreateView(LoginRequiredMixin, CreateView):
    model = Miles
    form_class = MileageForm
    template_name = 'finance/mileage_form.html'
    success_url = reverse_lazy('mileage_log')

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Mileage entry added successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'mileage'
        return context


class MileageUpdateView(LoginRequiredMixin, UpdateView):
    model = Miles
    form_class = MileageForm
    template_name = 'finance/mileage_form.html'
    success_url = reverse_lazy('mileage_log')

    def get_queryset(self):
        return Miles.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Mileage entry updated successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'mileage'
        return context


class MileageDeleteView(LoginRequiredMixin, DeleteView):
    model = Miles
    template_name = 'finance/mileage_confirm_delete.html'
    success_url = reverse_lazy('mileage_log')

    def get_queryset(self):
        return Miles.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Mileage entry deleted successfully!")
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'mileage'
        return context



@login_required
def update_mileage_rate(request):
    mileage_rate = MileageRate.objects.first() or MileageRate(rate=0.70)
    if request.method == 'POST':
        form = MileageRateForm(request.POST, instance=mileage_rate)
        if form.is_valid():
            form.save()
            messages.success(request, "Mileage rate updated successfully!")
            return redirect('mileage_log')
        else:
            messages.error(request, "Error updating mileage rate. Please check the form.")
    else:
        form = MileageRateForm(instance=mileage_rate)
    context = {'form': form, 'current_page': 'mileage'}
    return render(request, 'finance/update_mileage_rate.html', context)


# ---------------------------------------------------------------------------------------------------------------  Keywords


class KeywordListView(LoginRequiredMixin, ListView):
    model = Keyword
    template_name = 'nhra/keyword_list.html'
    context_object_name = 'keywords'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'keywords'
        return context


class KeywordCreateView(LoginRequiredMixin, CreateView):
    model = Keyword
    form_class = KeywordForm
    template_name = 'nhra/keyword_form.html'
    success_url = reverse_lazy('keyword_list')

    def form_valid(self, form):
        messages.success(self.request, "Keyword added successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'keywords'
        return context


class KeywordUpdateView(LoginRequiredMixin, UpdateView):
    model = Keyword
    form_class = KeywordForm
    template_name = 'nhra/keyword_form.html'
    success_url = reverse_lazy('keyword_list')

    def form_valid(self, form):
        messages.success(self.request, "Keyword updated successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'keywords'
        return context


class KeywordDeleteView(LoginRequiredMixin, DeleteView):
    model = Keyword
    template_name = 'nhra/keyword_confirm_delete.html'
    success_url = reverse_lazy('keyword_list')

    def delete(self, request, *args, **kwargs):
        try:
            response = super().delete(request, *args, **kwargs)
            messages.success(self.request, "Keyword deleted successfully!")
            return response
        except models.ProtectedError:
            messages.error(self.request, "Cannot delete keyword due to related transactions.")
            return redirect('keyword_list')
        except Exception as e:
            logger.error(f"Error deleting keyword for user {request.user.id}: {e}")
            messages.error(self.request, "Error deleting keyword.")
            return redirect('keyword_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'keywords'
        return context


# ---------------------------------------------------------------------------------------------------------------  Recurring Transactions


class RecurringTransactionListView(LoginRequiredMixin, ListView):
    model = RecurringTransaction
    template_name = 'finance/recurring_list.html'
    context_object_name = 'recurring_transactions'

    def get_queryset(self):
        return RecurringTransaction.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'recurring transactions'
        return context



class RecurringTransactionCreateView(LoginRequiredMixin, CreateView):
    model = RecurringTransaction
    form_class = RecurringTransactionForm
    template_name = 'finance/recurring_form.html'
    success_url = reverse_lazy('recurring_transaction_list')
    context = { 'current_page': 'recurring transactions', }

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Recurring transaction added successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'recurring_transactions'
        return context


class RecurringTransactionUpdateView(LoginRequiredMixin, UpdateView):
    model = RecurringTransaction
    form_class = RecurringTransactionForm
    template_name = 'finance/recurring_form.html'
    success_url = reverse_lazy('recurring_transaction_list')
    context = { 'current_page': 'recurring transactions', }

    def get_queryset(self):
        return RecurringTransaction.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Recurring transaction updated successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'recurring_transactions'
        return context


class RecurringTransactionDeleteView(LoginRequiredMixin, DeleteView):
    model = RecurringTransaction
    template_name = 'finance/recurring_confirm_delete.html'
    success_url = reverse_lazy('recurring_transaction_list')
    context = { 'current_page': 'recurring transactions', }

    def get_queryset(self):
        return RecurringTransaction.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Recurring transaction deleted successfully!")
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'recurring_transactions'
        return context


@staff_member_required
def recurring_report_view(request):
    year = int(request.GET.get('year', now().year))
    months = range(1, 13)

    templates = RecurringTransaction.objects.filter(user=request.user).order_by('transaction')

    transactions = Transaction.objects.filter(
        recurring_template__in=templates,
        date__year=year
    ).values('recurring_template_id', 'date__month').annotate(total_amount=Sum('amount'))

    amount_map = {(t['recurring_template_id'], t['date__month']): t['total_amount'] for t in transactions}

    data = []
    for template in templates:
        row = {
            'template': template,
            'monthly_amounts': [
                amount_map.get((template.id, month), None) for month in months
            ]
        }
        data.append(row)

    context = {
        'data': data,
        'months': [month_name[m] for m in months],
        'year': year,
        'current_page': 'recurring_transactions'
    }
    return render(request, 'finance/recurring_report.html', context)



@staff_member_required
def run_monthly_recurring_view(request):
    today = now().date()
    created = 0
    skipped = 0

    try:
        with transaction.atomic():
            recurrences = RecurringTransaction.objects.filter(active=True, user=request.user)
            for r in recurrences:
                exists = Transaction.objects.filter(
                    user=r.user,
                    transaction=r.transaction,
                    date__year=today.year,
                    date__month=today.month
                ).exists()
                if exists:
                    skipped += 1
                    continue

                Transaction.objects.create(
                    date=today,
                    trans_type=r.trans_type,
                    category=r.category,
                    sub_cat=r.sub_cat,
                    amount=r.amount,
                    transaction=r.transaction,
                    team=r.team,
                    keyword=r.keyword,
                    tax=r.tax,
                    user=r.user,
       
                )
                created += 1

        messages.success(request, f"{created} recurring transactions created, {skipped} skipped.")
        return redirect('recurring_transaction_list')

    except Exception as e:
        logger.error(f"Error running monthly recurring for user {request.user.id}: {e}")
        messages.error(request, "Error running monthly recurring.")
        return redirect('recurring_transaction_list')



# ---------------------------------------------------------------------------------------------------------------  Receipts


@login_required
def receipts_list(request):
    query = request.GET.get('search', '')
    receipts = Transaction.objects.filter(user=request.user, receipt__isnull=False)

    if query:
        receipts = receipts.filter(
            Q(invoice_numb__icontains=query) |
            Q(transaction__icontains=query)
        )

    receipts = receipts.order_by('-date')
    paginator = Paginator(receipts, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'receipts': page_obj.object_list,
        'page_obj': page_obj,
        'request': request,
    }
    return render(request, 'finance/receipts_list.html', context)


@login_required
def receipt_detail(request, pk):
    receipt = get_object_or_404(Transaction, pk=pk, user=request.user, receipt__isnull=False)
    return render(request, 'finance/receipt_detail.html', {'receipt': receipt})