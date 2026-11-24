from rest_framework import serializers
from apps.billing.models import Service, Invoice, InvoiceItem, Payment

class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = '__all__'


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = ['id', 'invoice', 'item_type', 'description', 'quantity', 'unit_price', 'total_price']


class PaymentSerializer(serializers.ModelSerializer):
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'receipt_number', 'invoice', 'amount', 'payment_method',
            'payment_method_display', 'transaction_reference', 'received_by',
            'payment_date', 'notes'
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    patient_name = serializers.ReadOnlyField(source='patient.full_name')
    doctor_name = serializers.ReadOnlyField(source='doctor.name')

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'clinic', 'patient', 'patient_name',
            'doctor', 'doctor_name', 'subtotal', 'discount', 'tax_percent',
            'tax_amount', 'total_amount', 'paid_amount', 'balance_due',
            'status', 'due_date', 'notes', 'items', 'payments', 'created_at'
        ]
