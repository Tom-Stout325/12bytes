from django.core.management.base import BaseCommand
from finance.models import Transaction, Invoice

class Command(BaseCommand):
    help = "Match Transactions to Invoice objects using invoice_numb"

    def handle(self, *args, **kwargs):
        matched = 0
        missing = 0

        for tx in Transaction.objects.exclude(invoice_numb__isnull=True).exclude(invoice_numb=''):
            try:
                invoice = Invoice.objects.get(invoice_numb=tx.invoice_numb)
                tx.invoice = invoice
                tx.save()
                matched += 1
            except Invoice.DoesNotExist:
                self.stdout.write(f"❌ No matching invoice for {tx.invoice_numb}")
                missing += 1

        self.stdout.write(f"✅ Matched: {matched}")
        self.stdout.write(f"⚠️ Missing: {missing}")
