from django.db import models
from apps.core.models import TimeStampedModel

class BotIntent(TimeStampedModel):
    ACTION_CHOICES = [
        ('GREETING', 'Greeting & Options'),
        ('LIST_DOCTORS', 'List Available Doctors'),
        ('SHOW_SPECIALTIES', 'Show Specialties'),
        ('BOOK_APPOINTMENT', 'Appointment Booking Flow'),
        ('CHECK_STATUS', 'Check Existing Appointment'),
        ('CLINIC_INFO', 'Clinic Timings & Location'),
        ('HUMAN_HANDOFF', 'Transfer to Human'),
        ('FAQ', 'Answer FAQ'),
    ]

    name = models.CharField(max_length=100, unique=True)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, default='FAQ')
    keywords = models.TextField(help_text="Comma-separated trigger keywords, e.g.: doctor, timings, appointment")
    response_template = models.TextField(help_text="Standard reply template or instructions")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} -> {self.get_action_display()}"


class ClinicFAQ(TimeStampedModel):
    clinic = models.ForeignKey('clinics.Clinic', on_delete=models.CASCADE, related_name='faqs')
    question = models.CharField(max_length=255)
    answer = models.TextField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.question
