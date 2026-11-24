from django.contrib import admin
from apps.consultations.models import Consultation, PrescriptionItem

class PrescriptionItemInline(admin.TabularInline):
    model = PrescriptionItem
    extra = 1

@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ('id', 'patient', 'doctor', 'consultation_date', 'diagnosis', 'blood_pressure', 'pulse')
    search_fields = ('patient__first_name', 'patient__last_name', 'patient__phone', 'doctor__name', 'diagnosis')
    list_filter = ('doctor', 'consultation_date')
    inlines = [PrescriptionItemInline]
