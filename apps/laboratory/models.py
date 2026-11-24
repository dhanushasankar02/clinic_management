from django.db import models
from apps.core.models import TimeStampedModel

class LabTest(TimeStampedModel):
    CATEGORY_CHOICES = [
        ('HEMATOLOGY', 'Hematology'),
        ('BIOCHEMISTRY', 'Biochemistry / Metabolic'),
        ('MICROBIOLOGY', 'Microbiology / Serology'),
        ('PATHOLOGY', 'Clinical Pathology'),
        ('URINE', 'Urine & Renal Analysis'),
        ('RADIOLOGY', 'Radiology / Imaging'),
        ('OTHER', 'General / Other'),
    ]

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='HEMATOLOGY')
    sample_type = models.CharField(max_length=100, default='Blood / Serum')
    normal_range = models.CharField(max_length=100, help_text="e.g. 13.5 - 17.5 g/dL")
    unit = models.CharField(max_length=50, blank=True, help_text="e.g. mg/dL, g/dL, %")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=300.00)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.code}) - ₹{self.price}"

    class Meta:
        ordering = ['category', 'name']


class LabOrder(TimeStampedModel):
    PRIORITY_CHOICES = [
        ('ROUTINE', 'Routine'),
        ('URGENT', 'Urgent'),
        ('STAT', 'Emergency / STAT'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending Sample Collection'),
        ('SAMPLE_COLLECTED', 'Sample Collected'),
        ('IN_PROCESS', 'Testing in Process'),
        ('COMPLETED', 'Completed & Verified'),
        ('CANCELLED', 'Cancelled'),
    ]

    order_number = models.CharField(max_length=50, unique=True, blank=True)
    clinic = models.ForeignKey('clinics.Clinic', on_delete=models.CASCADE, related_name='lab_orders')
    patient = models.ForeignKey('patients.Patient', on_delete=models.CASCADE, related_name='lab_orders')
    doctor = models.ForeignKey('doctors.Doctor', on_delete=models.SET_NULL, null=True, blank=True, related_name='requested_lab_orders')
    consultation = models.ForeignKey('consultations.Consultation', on_delete=models.SET_NULL, null=True, blank=True, related_name='lab_orders')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='ROUTINE')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING')
    clinical_notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.order_number:
            self.order_number = f"LAB-{self.pk + 1000}"
            LabOrder.objects.filter(pk=self.pk).update(order_number=self.order_number)

    def __str__(self):
        return f"{self.order_number} - {self.patient.full_name} ({self.get_status_display()})"

    class Meta:
        ordering = ['-created_at']


class LabOrderItem(TimeStampedModel):
    FLAG_CHOICES = [
        ('PENDING', 'Pending Analysis'),
        ('NORMAL', 'Normal'),
        ('LOW', 'Low Flag (L)'),
        ('HIGH', 'High Flag (H)'),
        ('CRITICAL', 'Critical Alert (!)'),
    ]

    order = models.ForeignKey(LabOrder, on_delete=models.CASCADE, related_name='items')
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE)
    result_value = models.CharField(max_length=100, blank=True)
    flag = models.CharField(max_length=20, choices=FLAG_CHOICES, default='PENDING')
    technician_remarks = models.TextField(blank=True)
    tested_at = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    verified_by = models.CharField(max_length=100, blank=True)

    def save(self, *args, **kwargs):
        if self.result_value and self.flag == 'PENDING':
            self.flag = 'NORMAL'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.test.name} for {self.order.order_number}: {self.result_value or 'Pending'}"
