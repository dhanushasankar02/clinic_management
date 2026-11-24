from django.contrib import admin
from apps.laboratory.models import LabTest, LabOrder, LabOrderItem

class LabOrderItemInline(admin.TabularInline):
    model = LabOrderItem
    extra = 1

@admin.register(LabTest)
class LabTestAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'category', 'normal_range', 'unit', 'price', 'is_active')
    search_fields = ('name', 'code')
    list_filter = ('category', 'is_active')

@admin.register(LabOrder)
class LabOrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'patient', 'doctor', 'priority', 'status', 'created_at')
    search_fields = ('order_number', 'patient__first_name', 'patient__last_name')
    list_filter = ('status', 'priority')
    inlines = [LabOrderItemInline]
