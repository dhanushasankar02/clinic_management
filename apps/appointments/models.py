from django.db import models
from django.contrib.auth.models import User
from apps.core.models import TimeStampedModel

class Appointment(TimeStampedModel):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Confirmation'),
        ('CONFIRMED', 'Confirmed'),
        ('CHECKED_IN', 'Checked In'),
        ('WAITING', 'Waiting in Queue'),
        ('IN_CONSULTATION', 'In Consultation'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('REJECTED', 'Rejected'),
        ('BOOKED', 'Booked'),
        ('NO_SHOW', 'No Show'),
    ]

    SOURCE_CHOICES = [
        ('ONLINE', 'Patient Online Portal'),
        ('WHATSAPP', 'WhatsApp Bot'),
        ('WEB', 'Staff Web Portal'),
        ('PHONE', 'Phone Call'),
        ('WALK_IN', 'Walk In'),
    ]

    TYPE_CHOICES = [
        ('NEW', 'New Consultation'),
        ('FOLLOW_UP', 'Follow-up Consultation'),
    ]

    clinic = models.ForeignKey('clinics.Clinic', on_delete=models.CASCADE, related_name='appointments')
    appointment_id = models.CharField(max_length=30, blank=True, db_index=True)
    doctor = models.ForeignKey('doctors.Doctor', on_delete=models.CASCADE, related_name='appointments')
    patient = models.ForeignKey('patients.Patient', on_delete=models.CASCADE, related_name='appointments')
    department = models.ForeignKey('doctors.Specialty', on_delete=models.SET_NULL, null=True, blank=True, related_name='appointments')
    appointment_date = models.DateField(db_index=True)
    appointment_time = models.TimeField()
    appointment_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='NEW')
    token_number = models.CharField(max_length=20, blank=True, help_text="Daily Token Number e.g. T-01")
    check_in_time = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=15)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='BOOKED', db_index=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='WEB')
    reason = models.TextField(blank=True, default='General Consultation')
    notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.token_number and self.appointment_date:
            existing_count = Appointment.objects.filter(
                clinic=self.clinic,
                appointment_date=self.appointment_date
            ).count()
            self.token_number = f"T-{str(existing_count + 1).zfill(2)}"
        super().save(*args, **kwargs)
        if not self.appointment_id:
            self.appointment_id = f"APT-{self.pk + 1000}"
            Appointment.objects.filter(pk=self.pk).update(appointment_id=self.appointment_id)

    def __str__(self):
        token_str = f"[{self.token_number}] " if self.token_number else ""
        return f"{token_str}{self.patient.full_name} with Dr. {self.doctor.name} on {self.appointment_date} at {self.appointment_time}"

    class Meta:
        ordering = ['-appointment_date', '-appointment_time']
        indexes = [
            models.Index(fields=['clinic', 'appointment_date', 'status']),
        ]


class AppointmentNotification(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='appointment_notifications')
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    notification_type = models.CharField(max_length=30, default='BOOKED')

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message[:40]}"

    class Meta:
        ordering = ['-created_at']


def notify_doctor_appointment(appointment, event_type='BOOKED'):
    """
    Sends an appointment notification EXCLUSIVELY to the assigned doctor.
    No other doctor receives or sees this notification.
    """
    if not appointment:
        return None
    doctor = appointment.doctor
    if not doctor or not doctor.user:
        return None

    patient_name = appointment.patient.full_name if appointment.patient else "Patient"
    appt_date_str = str(appointment.appointment_date)
    appt_time_str = str(appointment.appointment_time)[:5] if appointment.appointment_time else ""
    token_str = f" [Token #{appointment.token_number}]" if appointment.token_number else ""
    reason_str = f" - Reason: {appointment.reason}" if appointment.reason else ""

    if event_type == 'BOOKED':
        msg = f"New Appointment Assigned: {patient_name} has booked an appointment with you on {appt_date_str} at {appt_time_str}{token_str}{reason_str}."
    elif event_type == 'CONFIRMED':
        msg = f"Appointment Confirmed: {patient_name} is confirmed for {appt_date_str} at {appt_time_str}{token_str}."
    elif event_type == 'CANCELLED':
        msg = f"Appointment Cancelled: Visit for {patient_name} on {appt_date_str} at {appt_time_str} has been cancelled."
    elif event_type == 'RESCHEDULED':
        msg = f"Appointment Rescheduled: {patient_name} rescheduled to {appt_date_str} at {appt_time_str}{token_str}."
    elif event_type == 'REJECTED':
        msg = f"Appointment Rejected: Request for {patient_name} on {appt_date_str} at {appt_time_str} was rejected."
    else:
        msg = f"Appointment Update: {patient_name} on {appt_date_str} at {appt_time_str}{token_str}."

    return AppointmentNotification.objects.create(
        user=doctor.user,
        appointment=appointment,
        message=msg,
        notification_type=event_type
    )
