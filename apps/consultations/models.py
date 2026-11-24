from django.db import models
from apps.core.models import TimeStampedModel
from decimal import Decimal

class Consultation(TimeStampedModel):
    patient = models.ForeignKey('patients.Patient', on_delete=models.CASCADE, related_name='consultations')
    doctor = models.ForeignKey('doctors.Doctor', on_delete=models.CASCADE, related_name='consultations')
    appointment = models.OneToOneField('appointments.Appointment', on_delete=models.SET_NULL, null=True, blank=True, related_name='consultation')
    consultation_date = models.DateTimeField(auto_now_add=True)
    
    # Vitals
    temperature = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, help_text="°F")
    pulse = models.PositiveIntegerField(null=True, blank=True, help_text="bpm")
    blood_pressure = models.CharField(max_length=20, blank=True, help_text="Systolic/Diastolic e.g. 120/80")
    respiratory_rate = models.PositiveIntegerField(null=True, blank=True, help_text="breaths/min")
    spo2 = models.PositiveIntegerField(null=True, blank=True, help_text="% oxygen saturation")
    height_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    bmi = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)

    # Clinical Notes
    chief_complaints = models.TextField(help_text="Primary symptoms and duration")
    examination_notes = models.TextField(blank=True, help_text="Physical examination findings")
    diagnosis = models.TextField(help_text="Confirmed diagnosis or ICD notes")
    treatment_plan = models.TextField(blank=True, help_text="Advice, lifestyle modifications, follow up")
    clinical_notes = models.TextField(blank=True)
    follow_up_date = models.DateField(null=True, blank=True)

    def clean(self):
        super().clean()
        if self.respiratory_rate is not None and self.respiratory_rate < 0:
            self.respiratory_rate = None
        if self.pulse is not None and self.pulse < 0:
            self.pulse = None
        if self.spo2 is not None and self.spo2 < 0:
            self.spo2 = None
        if self.temperature is not None and self.temperature < 0:
            self.temperature = None
        if self.height_cm is not None and self.height_cm < 0:
            self.height_cm = None
        if self.weight_kg is not None and self.weight_kg < 0:
            self.weight_kg = None

    def save(self, *args, **kwargs):
        # Auto sanitize any negative or invalid vitals before hitting database CHECK constraints
        if self.respiratory_rate is not None and self.respiratory_rate < 0:
            self.respiratory_rate = None
        if self.pulse is not None and self.pulse < 0:
            self.pulse = None
        if self.spo2 is not None and self.spo2 < 0:
            self.spo2 = None
        if self.temperature is not None and self.temperature < 0:
            self.temperature = None
        if self.height_cm is not None and self.height_cm < 0:
            self.height_cm = None
        if self.weight_kg is not None and self.weight_kg < 0:
            self.weight_kg = None

        if self.height_cm and self.weight_kg and self.height_cm > 0:
            height_m = self.height_cm / Decimal(100)
            self.bmi = round(self.weight_kg / (height_m * height_m), 1)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Consultation: {self.patient.full_name} by Dr. {self.doctor.name} on {self.created_at.strftime('%Y-%m-%d')}"

    class Meta:
        ordering = ['-created_at']


class PrescriptionItem(TimeStampedModel):
    ROUTE_CHOICES = [
        ('Oral', 'Oral'),
        ('Topical', 'Topical / External'),
        ('IV', 'Intravenous (IV)'),
        ('IM', 'Intramuscular (IM)'),
        ('Inhalation', 'Inhalation'),
        ('Drops', 'Drops'),
    ]

    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name='prescriptions')
    medicine_name = models.CharField(max_length=200)
    dosage = models.CharField(max_length=50, default="1 tablet")
    route = models.CharField(max_length=50, choices=ROUTE_CHOICES, default='Oral')
    frequency = models.CharField(max_length=50, default="1-0-1", help_text="e.g. 1-0-1, Once daily, SOS")
    duration_days = models.PositiveIntegerField(default=5)
    instructions = models.CharField(max_length=255, blank=True, default="After food")

    def __str__(self):
        return f"{self.medicine_name} - {self.dosage} ({self.frequency} x {self.duration_days} days)"

    class Meta:
        ordering = ['id']
