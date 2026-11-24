from django.db import models
from apps.core.models import TimeStampedModel
from decimal import Decimal

class Service(TimeStampedModel):
    CATEGORY_CHOICES = [
        ('CONSULTATION', 'Doctor Consultation'),
        ('PROCEDURE', 'Clinical Procedure / Dressing'),
        ('LAB', 'Laboratory Test Fee'),
        ('PHARMACY', 'Pharmacy Dispense Fee'),
        ('NURSING', 'Nursing / Day Care'),
        ('OTHER', 'General / Other'),
    ]

    clinic = models.ForeignKey('clinics.Clinic', on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='CONSULTATION')
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - ₹{self.fee}"

    class Meta:
        ordering = ['name']


class Invoice(TimeStampedModel):
    STATUS_CHOICES = [
        ('UNPAID', 'Unpaid / Pending'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('PAID', 'Fully Paid'),
        ('CANCELLED', 'Cancelled / Void'),
    ]

    invoice_number = models.CharField(max_length=50, unique=True, blank=True)
    clinic = models.ForeignKey('clinics.Clinic', on_delete=models.CASCADE, related_name='invoices')
    patient = models.ForeignKey('patients.Patient', on_delete=models.CASCADE, related_name='invoices')
    doctor = models.ForeignKey('doctors.Doctor', on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    appointment = models.ForeignKey('appointments.Appointment', on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    consultation = models.ForeignKey('consultations.Consultation', on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="e.g. 5.00 for 5% GST")
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    balance_due = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UNPAID')
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def recalculate(self):
        items_total = sum((Decimal(str(item.total_price)) for item in self.items.all()), Decimal('0.00'))
        self.subtotal = items_total
        discount = Decimal(str(self.discount or 0))
        tax_pct = Decimal(str(self.tax_percent or 0))
        taxable = max(Decimal('0.00'), self.subtotal - discount)
        self.tax_amount = round(taxable * (tax_pct / Decimal(100)), 2)
        self.total_amount = taxable + self.tax_amount
        
        payments_total = sum((Decimal(str(p.amount)) for p in self.payments.model.objects.filter(invoice_id=self.pk)), Decimal('0.00'))
        self.paid_amount = payments_total
        self.balance_due = max(Decimal('0.00'), self.total_amount - self.paid_amount)
        
        if self.paid_amount >= self.total_amount and self.total_amount > 0:
            self.status = 'PAID'
        elif self.paid_amount > 0:
            self.status = 'PARTIALLY_PAID'
        else:
            self.status = 'UNPAID'
        Invoice.objects.filter(pk=self.pk).update(
            subtotal=self.subtotal,
            tax_amount=self.tax_amount,
            total_amount=self.total_amount,
            paid_amount=self.paid_amount,
            balance_due=self.balance_due,
            status=self.status,
        )

    def save(self, *args, **kwargs):
        subtotal = Decimal(str(self.subtotal or 0))
        discount = Decimal(str(self.discount or 0))
        tax_pct = Decimal(str(self.tax_percent or 0))
        paid = Decimal(str(self.paid_amount or 0))

        taxable = max(Decimal('0.00'), subtotal - discount)
        self.tax_amount = round(taxable * (tax_pct / Decimal(100)), 2)
        self.total_amount = taxable + self.tax_amount
        self.balance_due = max(Decimal('0.00'), self.total_amount - paid)
        super().save(*args, **kwargs)
        if not self.invoice_number:
            self.invoice_number = f"INV-{self.pk + 1000}"
            Invoice.objects.filter(pk=self.pk).update(invoice_number=self.invoice_number)

    def __str__(self):
        return f"{self.invoice_number} - {self.patient.full_name} (₹{self.total_amount} | {self.get_status_display()})"

    class Meta:
        ordering = ['-created_at']


class InvoiceItem(TimeStampedModel):
    ITEM_TYPE_CHOICES = [
        ('CONSULTATION', 'Consultation Fee'),
        ('PROCEDURE', 'Procedure Fee'),
        ('LAB', 'Laboratory Test'),
        ('PHARMACY', 'Medicine / Pharmacy'),
        ('OTHER', 'General / Other'),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=30, choices=ITEM_TYPE_CHOICES, default='CONSULTATION')
    description = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} ({self.quantity} x ₹{self.unit_price} = ₹{self.total_price})"


class Payment(TimeStampedModel):
    METHOD_CHOICES = [
        ('CASH', 'Cash'),
        ('UPI', 'UPI / QR Code'),
        ('CARD', 'Credit / Debit Card'),
        ('NET_BANKING', 'Net Banking / Transfer'),
        ('OTHER', 'Other'),
    ]

    receipt_number = models.CharField(max_length=50, unique=True, blank=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=30, choices=METHOD_CHOICES, default='CASH')
    transaction_reference = models.CharField(max_length=100, blank=True, help_text="UPI Ref / Txn ID")
    received_by = models.CharField(max_length=100, default='Accountant')
    payment_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.receipt_number:
            self.receipt_number = f"REC-{self.pk + 1000}"
            Payment.objects.filter(pk=self.pk).update(receipt_number=self.receipt_number)
        self.invoice.recalculate()

    def __str__(self):
        return f"{self.receipt_number} - ₹{self.amount} ({self.get_payment_method_display()}) for {self.invoice.invoice_number}"

    class Meta:
        ordering = ['-payment_date']
