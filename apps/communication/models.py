from django.db import models
from apps.core.models import TimeStampedModel

class WhatsAppConversation(TimeStampedModel):
    STATUS_CHOICES = [
        ('BOT', 'Handled by AI Bot'),
        ('AGENT', 'Human Agent Escalation'),
        ('RESOLVED', 'Resolved / Closed'),
    ]

    clinic = models.ForeignKey('clinics.Clinic', on_delete=models.CASCADE, related_name='conversations')
    patient = models.ForeignKey('patients.Patient', on_delete=models.SET_NULL, null=True, blank=True, related_name='conversations')
    phone_number = models.CharField(max_length=20, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='BOT')
    last_message = models.TextField(blank=True)
    last_message_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Chat with {self.phone_number} ({self.get_status_display()})"

    class Meta:
        ordering = ['-last_message_at']
        unique_together = ('clinic', 'phone_number')


class WhatsAppMessage(TimeStampedModel):
    SENDER_CHOICES = [
        ('PATIENT', 'Patient'),
        ('BOT', 'AI Assistant'),
        ('AGENT', 'Clinic Agent'),
        ('SYSTEM', 'System Alert'),
    ]

    conversation = models.ForeignKey(WhatsAppConversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES)
    text = models.TextField()
    is_read = models.BooleanField(default=False)
    message_id = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"[{self.sender}] {self.text[:30]}"

    class Meta:
        ordering = ['created_at']
