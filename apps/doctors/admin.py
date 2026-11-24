from django.contrib import admin
from apps.doctors.models import Specialty, Doctor, DoctorSchedule

@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'icon')
    prepopulated_fields = {'slug': ('name',)}

class DoctorScheduleInline(admin.TabularInline):
    model = DoctorSchedule
    extra = 1

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('name', 'clinic', 'specialty', 'qualification', 'consultation_fee', 'is_available')
    list_filter = ('clinic', 'specialty', 'is_available')
    search_fields = ('name', 'phone', 'email')
    inlines = [DoctorScheduleInline]
