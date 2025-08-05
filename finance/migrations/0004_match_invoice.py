from django.db import migrations

def forward_migration(apps, schema_editor):
    Invoice = apps.get_model('finance', 'Invoice')
    InvoiceNumber = apps.get_model('finance', 'InvoiceNumber')

    for invoice in Invoice.objects.exclude(invoice_numb__isnull=True).exclude(invoice_numb=''):
        try:
            invoice_num_obj = InvoiceNumber.objects.get(invoice_numb=invoice.invoice_numb)
            invoice.invoice_number = invoice_num_obj
            invoice.save()
        except InvoiceNumber.DoesNotExist:
            continue

class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0003_invoicenumber_alter_invoice_invoice_numb_and_more'),  # ⬅️ CHANGE THIS to your actual latest migration name
    ]

    operations = [
        migrations.RunPython(forward_migration),
    ]
