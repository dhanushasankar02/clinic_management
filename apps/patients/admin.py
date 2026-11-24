from django.contrib import admin
from apps.patients.models import Patient, MedicalRecord

class MedicalRecordInline(admin.TabularInline):
    model = MedicalRecord
    extra = 0

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'clinic', 'phone', 'gender', 'blood_group', 'created_at')
    list_filter = ('clinic', 'gender', 'blood_group')
    search_fields = ('first_name', 'last_name', 'phone')
    inlines = [MedicalRecordInline]
