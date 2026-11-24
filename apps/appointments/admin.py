from django.contrib import admin
from apps.appointments.models import Appointment

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'appointment_date', 'appointment_time', 'status', 'source')
    list_filter = ('clinic', 'status', 'source', 'appointment_date')
    search_fields = ('patient__first_name', 'patient__last_name', 'doctor__name')
