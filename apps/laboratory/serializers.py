from rest_framework import serializers
from apps.laboratory.models import LabTest, LabOrder, LabOrderItem

class LabTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTest
        fields = '__all__'


class LabOrderItemSerializer(serializers.ModelSerializer):
    test_name = serializers.ReadOnlyField(source='test.name')
    test_code = serializers.ReadOnlyField(source='test.code')
    category = serializers.ReadOnlyField(source='test.get_category_display')
    normal_range = serializers.ReadOnlyField(source='test.normal_range')
    unit = serializers.ReadOnlyField(source='test.unit')

    class Meta:
        model = LabOrderItem
        fields = [
            'id', 'order', 'test', 'test_name', 'test_code', 'category',
            'result_value', 'flag', 'normal_range', 'unit',
            'technician_remarks', 'tested_at', 'is_verified', 'verified_by'
        ]


class LabOrderSerializer(serializers.ModelSerializer):
    items = LabOrderItemSerializer(many=True, read_only=True)
    patient_name = serializers.ReadOnlyField(source='patient.full_name')
    doctor_name = serializers.ReadOnlyField(source='doctor.name')

    class Meta:
        model = LabOrder
        fields = [
            'id', 'order_number', 'clinic', 'patient', 'patient_name',
            'doctor', 'doctor_name', 'consultation', 'priority', 'status',
            'clinical_notes', 'items', 'created_at'
        ]
