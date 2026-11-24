from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.clinics.models import Clinic, ClinicSetting

@login_required
def clinic_detail(request):
    is_super = request.user.is_superuser
    profile = getattr(request.user, 'profile', None)
    is_admin = is_super or (profile and profile.role in ['SUPER_ADMIN', 'CLINIC_ADMIN'])

    if not is_admin:
        messages.error(request, "Access restricted: Only Clinic Administrators can view or modify clinic settings.")
        return redirect('dashboard:index')

    clinic = Clinic.objects.first()
    settings, _ = ClinicSetting.objects.get_or_create(clinic=clinic) if clinic else (None, False)

    if request.method == 'POST' and clinic:
        clinic.name = request.POST.get('name', clinic.name)
        clinic.phone = request.POST.get('phone', clinic.phone)
        clinic.email = request.POST.get('email', clinic.email)
        clinic.address = request.POST.get('address', clinic.address)
        clinic.whatsapp_number = request.POST.get('whatsapp_number', clinic.whatsapp_number)
        clinic.save()

        if settings:
            settings.enable_whatsapp_bot = 'enable_whatsapp_bot' in request.POST
            settings.auto_confirm_appointments = 'auto_confirm_appointments' in request.POST
            settings.save()

        messages.success(request, 'Clinic settings updated successfully.')
        return redirect('clinics:detail')

    return render(request, 'clinics/detail.html', {'clinic': clinic, 'settings': settings})
