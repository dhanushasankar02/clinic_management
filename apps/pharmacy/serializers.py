from rest_framework import serializers
from apps.pharmacy.models import Medicine, MedicineBatch, DispenseRecord, DispenseItem

class MedicineBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicineBatch
        fields = '__all__'


class MedicineSerializer(serializers.ModelSerializer):
    batches = MedicineBatchSerializer(many=True, read_only=True)
    total_stock = serializers.ReadOnlyField()
    is_low_stock = serializers.ReadOnlyField()

    class Meta:
        model = Medicine
        fields = [
            'id', 'clinic', 'name', 'generic_name', 'category', 'dosage_form',
            'strength', 'unit_price', 'reorder_level', 'total_stock',
            'is_low_stock', 'is_active', 'batches'
        ]


class DispenseItemSerializer(serializers.ModelSerializer):
    medicine_name = serializers.ReadOnlyField(source='batch.medicine.name')
    batch_number = serializers.ReadOnlyField(source='batch.batch_number')

    class Meta:
        model = DispenseItem
        fields = ['id', 'dispense', 'batch', 'medicine_name', 'batch_number', 'quantity', 'unit_price', 'total_price']


class DispenseRecordSerializer(serializers.ModelSerializer):
    items = DispenseItemSerializer(many=True, read_only=True)
    patient_name = serializers.ReadOnlyField(source='patient.full_name')

    class Meta:
        model = DispenseRecord
        fields = ['id', 'dispense_number', 'clinic', 'patient', 'patient_name', 'consultation', 'dispensed_by', 'total_amount', 'notes', 'items', 'created_at']
