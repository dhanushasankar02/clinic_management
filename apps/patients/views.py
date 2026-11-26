from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from rest_framework import viewsets
from apps.patients.models import Patient, MedicalRecord
from apps.patients.serializers import PatientSerializer
from apps.clinics.models import Clinic
from django.contrib.auth.decorators import login_required
from apps.accounts.decorators import role_required, get_dashboard_url_for_user

@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'DOCTOR', 'RECEPTIONIST', 'NURSE', 'PHARMACIST', 'LAB_TECH', 'ACCOUNTANT'])
def patient_list(request):
    clinic = Clinic.objects.first()
    search = request.GET.get('q', '').strip()
    patients = Patient.objects.filter(clinic=clinic)

    if search:
        patients = patients.filter(
            Q(phone__icontains=search) |
            Q(patient_id__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        dob = request.POST.get('date_of_birth') or None
        gender = request.POST.get('gender', 'M')
        blood_group = request.POST.get('blood_group', 'UNKNOWN')
        emergency_name = request.POST.get('emergency_contact_name', '').strip()
        emergency_phone = request.POST.get('emergency_contact_phone', '').strip()
        allergies = request.POST.get('allergies', '').strip()
        chronic = request.POST.get('chronic_conditions', '').strip()
        notes = request.POST.get('medical_notes', '').strip()
        address = request.POST.get('address', '').strip()

        if first_name and phone and clinic:
            patient, created = Patient.objects.get_or_create(
                clinic=clinic,
                phone=phone,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'date_of_birth': dob,
                    'gender': gender,
                    'blood_group': blood_group,
                    'emergency_contact_name': emergency_name,
                    'emergency_contact_phone': emergency_phone,
                    'allergies': allergies,
                    'chronic_conditions': chronic,
                    'medical_notes': notes,
                    'address': address
                }
            )
            if not created:
                patient.first_name = first_name
                patient.last_name = last_name
                if email: patient.email = email
                if dob: patient.date_of_birth = dob
                patient.gender = gender
                patient.blood_group = blood_group
                if emergency_name: patient.emergency_contact_name = emergency_name
                if emergency_phone: patient.emergency_contact_phone = emergency_phone
                if allergies: patient.allergies = allergies
                if chronic: patient.chronic_conditions = chronic
                if notes: patient.medical_notes = notes
                if address: patient.address = address
                patient.save()
                messages.info(request, f'Patient {patient.full_name} [{patient.patient_id}] is already registered. Opening complete medical history.')
                return redirect('patients:detail', pk=patient.pk)
            else:
                messages.success(request, f'Step 1 Complete: Patient {patient.full_name} registered successfully with ID: {patient.patient_id}! Now enter reception appointment.')
                return redirect(f"/appointments/?patient_id={patient.id}&new_patient=1")

    return render(request, 'patients/list.html', {
        'patients': patients,
        'search': search,
        'clinic': clinic
    })


@login_required
def patient_detail(request, pk):
    clinic = Clinic.objects.first()
    patient = get_object_or_404(Patient, pk=pk, clinic=clinic)
    profile = getattr(request.user, 'profile', None)
    role = profile.role if profile else None

    # If logged-in user is a patient
    if role == 'PATIENT':
        if patient.user == request.user:
            return redirect('portal:my_medical_records')
        messages.error(request, "Access restricted. You may only view your own patient profile.")
        return redirect('portal:dashboard')

    allowed_staff = ['SUPER_ADMIN', 'CLINIC_ADMIN', 'DOCTOR', 'RECEPTIONIST', 'NURSE', 'PHARMACIST', 'LAB_TECH', 'ACCOUNTANT']
    if not (request.user.is_superuser or role in allowed_staff):
        messages.error(request, "Access restricted. You do not have permission to view patient records.")
        return redirect(get_dashboard_url_for_user(request.user))

    appointments = patient.appointments.all().select_related('doctor')
    consultations = patient.consultations.prefetch_related('prescriptions', 'doctor').all()
    lab_orders = patient.lab_orders.prefetch_related('items__test').all()
    invoices = patient.invoices.prefetch_related('items', 'payments').all()
    dispensations = patient.pharmacy_dispensations.prefetch_related('items__batch__medicine').all()

    can_view_consultations = request.user.is_superuser or role in ['SUPER_ADMIN', 'CLINIC_ADMIN', 'DOCTOR', 'NURSE', 'RECEPTIONIST', 'PHARMACIST']
    can_view_laboratory = request.user.is_superuser or role in ['SUPER_ADMIN', 'CLINIC_ADMIN', 'LAB_TECH', 'DOCTOR', 'NURSE', 'RECEPTIONIST']
    can_view_pharmacy = request.user.is_superuser or role in ['SUPER_ADMIN', 'CLINIC_ADMIN', 'PHARMACIST', 'DOCTOR', 'RECEPTIONIST', 'NURSE']
    can_view_billing = request.user.is_superuser or role in ['SUPER_ADMIN', 'CLINIC_ADMIN', 'ACCOUNTANT', 'RECEPTIONIST', 'DOCTOR', 'PHARMACIST']

    return render(request, 'patients/detail.html', {
        'patient': patient,
        'appointments': appointments,
        'consultations': consultations,
        'lab_orders': lab_orders,
        'invoices': invoices,
        'dispensations': dispensations,
        'clinic': clinic,
        'can_view_consultations': can_view_consultations,
        'can_view_laboratory': can_view_laboratory,
        'can_view_pharmacy': can_view_pharmacy,
        'can_view_billing': can_view_billing,
    })


class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
