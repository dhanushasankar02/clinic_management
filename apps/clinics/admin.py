from django.contrib import admin
from apps.clinics.models import Clinic, ClinicSetting

@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'phone', 'city', 'is_active')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(ClinicSetting)
class ClinicSettingAdmin(admin.ModelAdmin):
    list_display = ('clinic', 'enable_whatsapp_bot', 'auto_confirm_appointments')
