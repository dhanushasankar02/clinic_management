from django.db import models
from django.db.models import Sum
from apps.core.models import TimeStampedModel
from datetime import date

class Medicine(TimeStampedModel):
    FORM_CHOICES = [
        ('TABLET', 'Tablet'),
        ('CAPSULE', 'Capsule'),
        ('SYRUP', 'Syrup / Oral Liquid'),
        ('INJECTION', 'Injection / Vial'),
        ('OINTMENT', 'Ointment / Gel'),
        ('DROPS', 'Eye / Ear Drops'),
        ('INHALER', 'Inhaler / Respules'),
        ('OTHER', 'Other'),
    ]

    CATEGORY_CHOICES = [
        ('ANALGESIC', 'Analgesic / Pain Relief'),
        ('ANTIBIOTIC', 'Antibiotic / Antimicrobial'),
        ('ANTIPYRETIC', 'Antipyretic / Fever'),
        ('ANTIHISTAMINE', 'Antihistamine / Allergy'),
        ('ANTIDIABETIC', 'Antidiabetic'),
        ('ANTIHYPERTENSIVE', 'Antihypertensive / Cardiac'),
        ('GASTRO', 'Gastrointestinal / Antacid'),
        ('VITAMIN', 'Vitamin / Supplement'),
        ('RESPIRATORY', 'Respiratory / Cough'),
        ('OTHER', 'General / Other'),
    ]

    clinic = models.ForeignKey('clinics.Clinic', on_delete=models.CASCADE, related_name='medicines')
    name = models.CharField(max_length=200, help_text="Brand Name e.g. Dolo 650")
    generic_name = models.CharField(max_length=200, help_text="Generic formula e.g. Paracetamol")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='ANALGESIC')
    dosage_form = models.CharField(max_length=50, choices=FORM_CHOICES, default='TABLET')
    strength = models.CharField(max_length=100, default='650mg')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=5.00, help_text="Default selling price per unit")
    reorder_level = models.PositiveIntegerField(default=30, help_text="Alert threshold for low stock")
    is_active = models.BooleanField(default=True)

    @property
    def total_stock(self):
        res = self.batches.filter(expiry_date__gte=date.today()).aggregate(total=Sum('quantity_in_stock'))
        return res['total'] or 0

    @property
    def is_low_stock(self):
        return self.total_stock <= self.reorder_level

    def __str__(self):
        return f"{self.name} ({self.strength}) - Stock: {self.total_stock}"

    class Meta:
        ordering = ['name']


class MedicineBatch(TimeStampedModel):
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name='batches')
    batch_number = models.CharField(max_length=50)
    expiry_date = models.DateField(db_index=True)
    quantity_in_stock = models.PositiveIntegerField(default=0)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=3.00)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=5.00)
    supplier = models.CharField(max_length=150, blank=True)

    @property
    def is_expired(self):
        return self.expiry_date < date.today()

    @property
    def is_near_expiry(self):
        from datetime import timedelta
        return date.today() <= self.expiry_date <= (date.today() + timedelta(days=60))

    def __str__(self):
        return f"{self.medicine.name} (Batch: {self.batch_number}, Qty: {self.quantity_in_stock}, Exp: {self.expiry_date})"

    class Meta:
        ordering = ['expiry_date']


class DispenseRecord(TimeStampedModel):
    dispense_number = models.CharField(max_length=50, unique=True, blank=True)
    clinic = models.ForeignKey('clinics.Clinic', on_delete=models.CASCADE, related_name='dispensations')
    patient = models.ForeignKey('patients.Patient', on_delete=models.CASCADE, related_name='pharmacy_dispensations')
    consultation = models.ForeignKey('consultations.Consultation', on_delete=models.SET_NULL, null=True, blank=True, related_name='dispensations')
    dispensed_by = models.CharField(max_length=100, default='Pharmacist')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.dispense_number:
            self.dispense_number = f"DSP-{self.pk + 1000}"
            DispenseRecord.objects.filter(pk=self.pk).update(dispense_number=self.dispense_number)

    def __str__(self):
        return f"{self.dispense_number} - {self.patient.full_name} (₹{self.total_amount})"

    class Meta:
        ordering = ['-created_at']


class DispenseItem(TimeStampedModel):
    dispense = models.ForeignKey(DispenseRecord, on_delete=models.CASCADE, related_name='items')
    batch = models.ForeignKey(MedicineBatch, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            # Deduct batch stock
            if self.batch.quantity_in_stock >= self.quantity:
                self.batch.quantity_in_stock -= self.quantity
            else:
                self.batch.quantity_in_stock = 0
            self.batch.save()

    def __str__(self):
        return f"{self.batch.medicine.name} x {self.quantity} = ₹{self.total_price}"
