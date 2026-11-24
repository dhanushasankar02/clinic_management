from django.contrib import admin
from apps.billing.models import Service, Invoice, InvoiceItem, Payment

class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1

class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'category', 'fee', 'is_active')
    search_fields = ('name', 'code')
    list_filter = ('category', 'is_active')

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'patient', 'doctor', 'total_amount', 'paid_amount', 'balance_due', 'status', 'created_at')
    search_fields = ('invoice_number', 'patient__first_name', 'patient__last_name')
    list_filter = ('status', 'created_at')
    inlines = [InvoiceItemInline, PaymentInline]

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'invoice', 'amount', 'payment_method', 'payment_date')
    search_fields = ('receipt_number', 'invoice__invoice_number')
