from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from decimal import Decimal
from rest_framework import viewsets
from apps.consultations.models import Consultation, PrescriptionItem
from apps.consultations.serializers import ConsultationSerializer, PrescriptionItemSerializer
from apps.patients.models import Patient
from apps.doctors.models import Doctor
from apps.appointments.models import Appointment
from apps.laboratory.models import LabTest, LabOrder, LabOrderItem
from apps.pharmacy.models import Medicine
from apps.accounts.decorators import role_required
from django.db import models

# REST API ViewSet
class ConsultationViewSet(viewsets.ModelViewSet):
    queryset = Consultation.objects.all().select_related('patient', 'doctor', 'appointment').prefetch_related('prescriptions')
    serializer_class = ConsultationSerializer


class PrescriptionItemViewSet(viewsets.ModelViewSet):
    queryset = PrescriptionItem.objects.all()
    serializer_class = PrescriptionItemSerializer


# Frontend Views
@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'DOCTOR', 'NURSE'])
def consultation_list(request):
    query = request.GET.get('q', '').strip()
    consultations = Consultation.objects.select_related('patient', 'doctor').all()
    if query:
        consultations = consultations.filter(
            models.Q(patient__first_name__icontains=query) |
            models.Q(patient__last_name__icontains=query) |
            models.Q(patient__phone__icontains=query) |
            models.Q(diagnosis__icontains=query)
        )
    return render(request, 'consultations/list.html', {
        'consultations': consultations,
        'query': query,
    })


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'DOCTOR', 'NURSE', 'RECEPTIONIST'])
def consultation_detail(request, pk):
    consultation = get_object_or_404(Consultation.objects.select_related('patient', 'doctor', 'appointment').prefetch_related('prescriptions'), pk=pk)
    lab_orders = consultation.lab_orders.prefetch_related('items__test').all()
    return render(request, 'consultations/detail.html', {
        'consultation': consultation,
        'lab_orders': lab_orders,
    })


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'DOCTOR', 'NURSE', 'PHARMACIST', 'RECEPTIONIST'])
def consultation_print_rx(request, pk):
    consultation = get_object_or_404(Consultation.objects.select_related('patient', 'doctor', 'appointment', 'patient__clinic').prefetch_related('prescriptions'), pk=pk)
    return render(request, 'consultations/print_rx.html', {
        'consultation': consultation,
        'clinic': consultation.patient.clinic,
    })


def _clean_pos_int(raw):
    if raw is None:
        return None
    val = str(raw).strip()
    if not val:
        return None
    try:
        n = int(val)
        return n if n >= 0 else None
    except (ValueError, TypeError):
        return None


def _clean_pos_dec(raw):
    if raw is None:
        return None
    val = str(raw).strip()
    if not val:
        return None
    try:
        d = Decimal(val)
        return d if d >= 0 else None
    except (ValueError, TypeError, Exception):
        return None


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'DOCTOR', 'NURSE', 'RECEPTIONIST'])
def consultation_create(request, appointment_id=None):
    patient_id = request.GET.get('patient_id') or request.POST.get('patient')
    appointment_id = appointment_id or request.GET.get('appointment_id') or request.POST.get('appointment')
    
    selected_patient = Patient.objects.filter(pk=patient_id).first() if patient_id else None
    selected_appointment = Appointment.objects.filter(pk=appointment_id).first() if appointment_id else None

    if request.method == 'POST':
        try:
            with transaction.atomic():
                patient = get_object_or_404(Patient, pk=request.POST.get('patient'))
                doctor = get_object_or_404(Doctor, pk=request.POST.get('doctor'))
                
                temp = request.POST.get('temperature') or None
                pulse = request.POST.get('pulse') or None
                bp = request.POST.get('blood_pressure', '').strip()
                rr = request.POST.get('respiratory_rate') or None
                spo2 = request.POST.get('spo2') or None
                height = request.POST.get('height_cm') or None
                weight = request.POST.get('weight_kg') or None

                appt = None
                if appointment_id:
                    appt = Appointment.objects.filter(pk=appointment_id).first()
                    if appt:
                        appt.status = 'COMPLETED'
                        appt.save()

                consultation = Consultation.objects.create(
                    patient=patient,
                    doctor=doctor,
                    appointment=appt,
                    temperature=_clean_pos_dec(temp),
                    pulse=_clean_pos_int(pulse),
                    blood_pressure=bp,
                    respiratory_rate=_clean_pos_int(rr),
                    spo2=_clean_pos_int(spo2),
                    height_cm=_clean_pos_dec(height),
                    weight_kg=_clean_pos_dec(weight),
                    chief_complaints=request.POST.get('chief_complaints', '').strip(),
                    examination_notes=request.POST.get('examination_notes', '').strip(),
                    diagnosis=request.POST.get('diagnosis', '').strip(),
                    treatment_plan=request.POST.get('treatment_plan', '').strip(),
                    clinical_notes=request.POST.get('clinical_notes', '').strip(),
                    follow_up_date=request.POST.get('follow_up_date') or None,
                )

                # Process Dynamic Prescriptions
                med_names = request.POST.getlist('med_name[]')
                dosages = request.POST.getlist('med_dosage[]')
                routes = request.POST.getlist('med_route[]')
                freqs = request.POST.getlist('med_frequency[]')
                durations = request.POST.getlist('med_duration[]')
                instructions = request.POST.getlist('med_instructions[]')

                for i in range(len(med_names)):
                    name = med_names[i].strip()
                    if name:
                        PrescriptionItem.objects.create(
                            consultation=consultation,
                            medicine_name=name,
                            dosage=dosages[i] if i < len(dosages) and dosages[i] else "1 tablet",
                            route=routes[i] if i < len(routes) and routes[i] else "Oral",
                            frequency=freqs[i] if i < len(freqs) and freqs[i] else "1-0-1",
                            duration_days=int(durations[i]) if i < len(durations) and durations[i].isdigit() else 5,
                            instructions=instructions[i] if i < len(instructions) else "After meals",
                        )

                # Process optional lab tests ordered
                selected_test_ids = request.POST.getlist('lab_tests[]')
                target_dest = request.POST.get('target_destination', '')

                if selected_test_ids:
                    lab_order = LabOrder.objects.create(
                        clinic=patient.clinic,
                        patient=patient,
                        doctor=doctor,
                        consultation=consultation,
                        priority='ROUTINE',
                        status='PENDING',
                        clinical_notes=f"Ordered during consultation: {consultation.diagnosis}"
                    )
                    for test_id in selected_test_ids:
                        test_obj = LabTest.objects.filter(pk=test_id).first()
                        if test_obj:
                            LabOrderItem.objects.create(
                                order=lab_order,
                                test=test_obj,
                                flag='PENDING'
                            )

                    messages.success(request, f"Doctor checkup complete for {patient.full_name}! Lab Order #{lab_order.order_number} created. Proceeding to Laboratory Investigation.")
                    return redirect('laboratory:detail', pk=lab_order.pk)
                else:
                    messages.success(request, f"Doctor checkup complete for {patient.full_name}! No lab tests required. Proceeding to Pharmacy for medicine dispensation.")
                    return redirect(f"/pharmacy/dispense/new/?patient_id={patient.pk}&consultation_id={consultation.pk}")

        except Exception as e:
            messages.error(request, f"Error saving consultation: {str(e)}")

    patients = Patient.objects.all()
    doctors = Doctor.objects.all()
    lab_tests = LabTest.objects.filter(is_active=True)
    available_medicines = Medicine.objects.filter(is_active=True)

    return render(request, 'consultations/create.html', {
        'patients': patients,
        'doctors': doctors,
        'lab_tests': lab_tests,
        'available_medicines': available_medicines,
        'selected_patient': selected_patient,
        'selected_appointment': selected_appointment,
    })
