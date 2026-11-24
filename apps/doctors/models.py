from django.db import models
from django.contrib.auth.models import User
from apps.core.models import TimeStampedModel

class Specialty(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='stethoscope')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Specialties'
        ordering = ['name']


class Doctor(TimeStampedModel):
    clinic = models.ForeignKey('clinics.Clinic', on_delete=models.CASCADE, related_name='doctors')
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='doctor_profile')
    name = models.CharField(max_length=150)
    specialty = models.ForeignKey(Specialty, on_delete=models.SET_NULL, null=True, related_name='doctors')
    qualification = models.CharField(max_length=150, default='MBBS, MD')
    experience_years = models.PositiveIntegerField(default=5)
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to='doctor_profiles/', null=True, blank=True)
    photo_url = models.CharField(max_length=500, blank=True)
    is_available = models.BooleanField(default=True)

    @property
    def get_photo_url(self):
        if self.photo:
            try:
                return self.photo.url
            except Exception:
                pass
        if self.photo_url:
            return self.photo_url
        slug = self.name.lower().replace(' ', '_').replace('.', '').replace('dr_', '').strip()
        import os
        from django.conf import settings
        target_file = f"{slug}.jpg"
        if os.path.exists(os.path.join(settings.MEDIA_ROOT, 'doctor_profiles', target_file)):
            return f"{settings.MEDIA_URL}doctor_profiles/{target_file}"
        for candidate in ['arun_sharma', 'priya_nair', 'sarah_jenkins', 'vikram_mehta']:
            if candidate in slug:
                return f"{settings.MEDIA_URL}doctor_profiles/{candidate}.jpg"
        return f"https://ui-avatars.com/api/?name={self.name.replace(' ', '+')}&background=0D9488&color=fff&size=200&bold=true"

    @property
    def full_name(self):
        prefix = "Dr. " if not self.name.startswith("Dr.") else ""
        return f"{prefix}{self.name}"

    def __str__(self):
        return f"Dr. {self.name} ({self.specialty.name if self.specialty else 'General'})"

    class Meta:
        ordering = ['name']


class DoctorSchedule(TimeStampedModel):
    DAYS_OF_WEEK = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='schedules')
    day_of_week = models.IntegerField(choices=DAYS_OF_WEEK)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_duration = models.PositiveIntegerField(default=15, help_text="Duration in minutes")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.doctor.name} - {self.get_day_of_week_display()} ({self.start_time} - {self.end_time})"

    class Meta:
        unique_together = ('doctor', 'day_of_week', 'start_time')
        ordering = ['day_of_week', 'start_time']


class DoctorAvailability(TimeStampedModel):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='availabilities')
    working_day = models.IntegerField(choices=DoctorSchedule.DAYS_OF_WEEK, null=True, blank=True)
    available_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(default="09:00:00")
    end_time = models.TimeField(default="17:00:00")
    slot_duration = models.PositiveIntegerField(default=15, help_text="Duration in minutes")
    break_start = models.TimeField(null=True, blank=True)
    break_end = models.TimeField(null=True, blank=True)
    is_available = models.BooleanField(default=True)
    is_leave = models.BooleanField(default=False)
    notes = models.CharField(max_length=255, blank=True)

    def __str__(self):
        day_str = self.get_working_day_display() if self.working_day is not None else str(self.available_date)
        return f"{self.doctor.name} - {day_str} ({self.start_time} - {self.end_time})"

    class Meta:
        verbose_name_plural = 'Doctor Availabilities'
        ordering = ['doctor', 'working_day', 'available_date']
