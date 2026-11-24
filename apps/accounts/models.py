from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from apps.core.models import TimeStampedModel

class UserProfile(TimeStampedModel):
    ROLE_CHOICES = [
        ('SUPER_ADMIN', 'Super Admin'),
        ('CLINIC_ADMIN', 'Clinic Administrator'),
        ('DOCTOR', 'Doctor'),
        ('RECEPTIONIST', 'Receptionist'),
        ('NURSE', 'Nurse'),
        ('LAB_TECH', 'Lab Technician'),
        ('PHARMACIST', 'Pharmacist'),
        ('ACCOUNTANT', 'Accountant'),
        ('INVENTORY_MGR', 'Inventory Manager'),
        ('PATIENT', 'Patient'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    clinic = models.ForeignKey('clinics.Clinic', on_delete=models.SET_NULL, null=True, blank=True, related_name='staff')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='CLINIC_ADMIN')
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"


class LoginAuditLog(TimeStampedModel):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('LOGGED_OUT', 'Logged Out'),
        ('FAILED', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='login_logs')
    username_attempted = models.CharField(max_length=150, blank=True)
    email = models.CharField(max_length=254, blank=True)
    role = models.CharField(max_length=50, blank=True)
    session_key = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    login_time = models.DateTimeField(default=timezone.now)
    last_activity = models.DateTimeField(null=True, blank=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')

    def get_user_display_name(self):
        if self.user:
            return self.user.get_full_name() or self.user.username
        return self.username_attempted or "Unknown"

    def get_user_email(self):
        if self.user and self.user.email:
            return self.user.email
        return self.email or "-"

    def __str__(self):
        return f"{self.get_user_display_name()} ({self.role}) - {self.status} at {self.login_time.strftime('%Y-%m-%d %H:%M:%S')}"

    class Meta:
        ordering = ['-login_time']


class SystemAuditLog(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='system_actions')
    action = models.CharField(max_length=100)
    module = models.CharField(max_length=50, default='General')
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        uname = self.user.username if self.user else 'System'
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {uname} - {self.action} ({self.module})"

    class Meta:
        ordering = ['-timestamp']
