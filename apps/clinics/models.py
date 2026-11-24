from django.db import models
from apps.core.models import TimeStampedModel

class Clinic(TimeStampedModel):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, default='Main City')
    whatsapp_number = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class ClinicSetting(TimeStampedModel):
    clinic = models.OneToOneField(Clinic, on_delete=models.CASCADE, related_name='settings')
    enable_whatsapp_bot = models.BooleanField(default=True)
    auto_confirm_appointments = models.BooleanField(default=False)
    reminder_hours_before = models.PositiveIntegerField(default=24)
    cancellation_window_hours = models.PositiveIntegerField(default=2)
    default_slot_duration = models.PositiveIntegerField(default=15)

    def __str__(self):
        return f"Settings for {self.clinic.name}"
