from django.db import models
from django.contrib.auth.models import User
from apps.core.models import TimeStampedModel
from datetime import date

class Patient(TimeStampedModel):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]

    BLOOD_GROUPS = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('UNKNOWN', 'Unknown'),
    ]

    clinic = models.ForeignKey('clinics.Clinic', on_delete=models.CASCADE, related_name='patients')
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='patient_record')
    patient_id = models.CharField(max_length=30, blank=True, db_index=True, help_text="Unique Patient MRN ID")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, db_index=True)
    email = models.EmailField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='M')
    blood_group = models.CharField(max_length=10, choices=BLOOD_GROUPS, default='UNKNOWN')
    address = models.TextField(blank=True)
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    allergies = models.TextField(blank=True)
    chronic_conditions = models.TextField(blank=True)
    medical_notes = models.TextField(blank=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def name(self):
        return self.full_name

    @property
    def age(self):
        if self.date_of_birth:
            today = date.today()
            return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        return "N/A"

    def ensure_user_account(self, password='patient123'):
        if self.user:
            return self.user
        from apps.accounts.models import UserProfile
        from django.contrib.auth.models import User
        base_name = self.first_name.lower().strip().replace(' ', '_') if self.first_name else 'patient'
        base_name = ''.join(c for c in base_name if c.isalnum() or c == '_') or 'patient'
        
        # Reuse existing unattached patient user if one already exists
        existing_u = User.objects.filter(username=base_name).first()
        if existing_u and (not hasattr(existing_u, 'patient_record') or existing_u.patient_record is None) and not existing_u.is_staff and not existing_u.is_superuser:
            self.user = existing_u
            UserProfile.objects.get_or_create(user=existing_u, defaults={'clinic': self.clinic, 'role': 'PATIENT', 'phone': self.phone})
            Patient.objects.filter(pk=self.pk).update(user=existing_u)
            return existing_u

        clean_phone = ''.join(c for c in (self.phone or '') if c.isdigit())
        phone_suffix = clean_phone[-4:] if len(clean_phone) >= 4 else str(self.pk or 1)
        phone_uname = f"{base_name}_{phone_suffix}"
        existing_phone_u = User.objects.filter(username=phone_uname).first()
        if existing_phone_u and (not hasattr(existing_phone_u, 'patient_record') or existing_phone_u.patient_record is None) and not existing_phone_u.is_staff and not existing_phone_u.is_superuser:
            self.user = existing_phone_u
            UserProfile.objects.get_or_create(user=existing_phone_u, defaults={'clinic': self.clinic, 'role': 'PATIENT', 'phone': self.phone})
            Patient.objects.filter(pk=self.pk).update(user=existing_phone_u)
            return existing_phone_u

        uname = base_name
        if User.objects.filter(username=uname).exists():
            uname = phone_uname
            counter = 1
            while User.objects.filter(username=uname).exists():
                uname = f"{base_name}_{phone_suffix}_{counter}"
                counter += 1

        u = User.objects.create_user(
            username=uname,
            email=self.email or '',
            password=password,
            first_name=self.first_name,
            last_name=self.last_name
        )
        UserProfile.objects.create(
            user=u,
            clinic=self.clinic,
            role='PATIENT',
            phone=self.phone
        )
        self.user = u
        Patient.objects.filter(pk=self.pk).update(user=u)
        return u

    def delete(self, *args, **kwargs):
        u = self.user
        super().delete(*args, **kwargs)
        if u and not u.is_staff and not u.is_superuser:
            u.delete()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.patient_id:
            self.patient_id = f"PAT-{self.pk + 1000}"
            Patient.objects.filter(pk=self.pk).update(patient_id=self.patient_id)
        if not self.user:
            self.ensure_user_account()

    def __str__(self):
        mrn = f"[{self.patient_id}] " if self.patient_id else ""
        return f"{mrn}{self.full_name} ({self.phone})"

    class Meta:
        ordering = ['first_name', 'last_name']
        unique_together = ('clinic', 'phone')


class MedicalRecord(TimeStampedModel):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='medical_records')
    doctor = models.ForeignKey('doctors.Doctor', on_delete=models.SET_NULL, null=True, related_name='prescribed_records')
    diagnosis = models.TextField()
    prescription = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Record for {self.patient.full_name} on {self.created_at.strftime('%Y-%m-%d')}"
