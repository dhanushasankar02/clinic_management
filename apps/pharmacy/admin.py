from django.contrib import admin
from apps.pharmacy.models import Medicine, MedicineBatch, DispenseRecord, DispenseItem

class MedicineBatchInline(admin.TabularInline):
    model = MedicineBatch
    extra = 1

@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ('name', 'generic_name', 'category', 'dosage_form', 'unit_price', 'total_stock', 'is_low_stock')
    search_fields = ('name', 'generic_name')
    list_filter = ('category', 'dosage_form')
    inlines = [MedicineBatchInline]

@admin.register(DispenseRecord)
class DispenseRecordAdmin(admin.ModelAdmin):
    list_display = ('dispense_number', 'patient', 'total_amount', 'dispensed_by', 'created_at')
    search_fields = ('dispense_number', 'patient__first_name', 'patient__last_name')
