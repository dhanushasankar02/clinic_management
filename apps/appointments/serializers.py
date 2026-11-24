from rest_framework import serializers
from apps.appointments.models import Appointment

class AppointmentSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    specialty_name = serializers.CharField(source='doctor.specialty.name', read_only=True)
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    patient_phone = serializers.CharField(source='patient.phone', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id', 'clinic', 'doctor', 'doctor_name', 'specialty_name',
            'patient', 'patient_name', 'patient_phone', 'appointment_date',
            'appointment_time', 'duration_minutes', 'status', 'status_display',
            'source', 'reason', 'notes', 'created_at'
        ]
