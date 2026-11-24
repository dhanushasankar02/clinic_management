from rest_framework import serializers
from apps.consultations.models import Consultation, PrescriptionItem
from apps.patients.serializers import PatientSerializer
from apps.doctors.serializers import DoctorSerializer

class PrescriptionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrescriptionItem
        fields = ['id', 'medicine_name', 'dosage', 'route', 'frequency', 'duration_days', 'instructions']


class ConsultationSerializer(serializers.ModelSerializer):
    prescriptions = PrescriptionItemSerializer(many=True, read_only=True)
    patient_name = serializers.ReadOnlyField(source='patient.full_name')
    doctor_name = serializers.ReadOnlyField(source='doctor.name')

    class Meta:
        model = Consultation
        fields = [
            'id', 'patient', 'patient_name', 'doctor', 'doctor_name',
            'appointment', 'consultation_date', 'temperature', 'pulse',
            'blood_pressure', 'respiratory_rate', 'spo2', 'height_cm',
            'weight_kg', 'bmi', 'chief_complaints', 'examination_notes',
            'diagnosis', 'treatment_plan', 'clinical_notes', 'follow_up_date',
            'prescriptions', 'created_at'
        ]
