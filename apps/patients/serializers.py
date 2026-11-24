from rest_framework import serializers
from apps.patients.models import Patient, MedicalRecord

class PatientSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Patient
        fields = [
            'id', 'clinic', 'first_name', 'last_name', 'full_name',
            'phone', 'email', 'date_of_birth', 'gender', 'blood_group',
            'address', 'allergies', 'medical_notes', 'created_at'
        ]

class MedicalRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalRecord
        fields = '__all__'
