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
@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'DOCTOR', 'NURSE', 'RECEPTIONIST', 'PHARMACIST', 'LAB_TECH', 'ACCOUNTANT'])
def consultation_list(request):
    query = request.GET.get('q', '').strip()
    profile = getattr(request.user, 'profile', None)
    role = profile.role if profile else None
    current_doctor = getattr(request.user, 'doctor_profile', None) or Doctor.objects.filter(user=request.user).first()

    consultations = Consultation.objects.select_related('patient', 'doctor').all()
    if role == 'DOCTOR' and current_doctor and request.GET.get('all') != '1':
        consultations = consultations.filter(doctor=current_doctor)

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
        'current_doctor': current_doctor,
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
    from apps.clinics.models import Clinic
    clinic = Clinic.objects.first()
    patient_id = request.GET.get('patient_id') or request.POST.get('patient')
    appointment_id = appointment_id or request.GET.get('appointment_id') or request.POST.get('appointment')
    
    selected_patient = Patient.objects.filter(pk=patient_id).first() if patient_id else None
    selected_appointment = Appointment.objects.filter(pk=appointment_id).first() if appointment_id else None

    profile = getattr(request.user, 'profile', None)
    role = profile.role if profile else None
    current_doctor = getattr(request.user, 'doctor_profile', None) or Doctor.objects.filter(user=request.user).first()

    # Identify the specific attending doctor:
    # 1. From selected appointment (the booked doctor)
    # 2. Or from the currently logged in doctor
    attending_doctor = None
    if selected_appointment and selected_appointment.doctor:
        attending_doctor = selected_appointment.doctor
    elif role == 'DOCTOR' and current_doctor:
        attending_doctor = current_doctor

    # Find the NEXT patient in queue waiting for this specific doctor
    next_waiting_appt = None
    if attending_doctor:
        exclude_ids = [selected_appointment.pk] if selected_appointment else []
        next_waiting_appt = Appointment.objects.filter(
            clinic=clinic,
            doctor=attending_doctor,
            status__in=['WAITING', 'CHECKED_IN']
        ).exclude(pk__in=exclude_ids).select_related('patient', 'doctor').order_by('check_in_time', 'appointment_time', 'id').first()

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

                target_dest = request.POST.get('target_destination', '').strip()
                no_followup = request.POST.get('no_followup_needed') in ['1', 'on', 'true', True] or target_dest == 'all_good'
                follow_up = None if no_followup else (request.POST.get('follow_up_date') or None)

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
                    chief_complaints=request.POST.get('chief_complaints', '').strip() or 'Routine checkup / wellness evaluation',
                    examination_notes=request.POST.get('examination_notes', '').strip(),
                    diagnosis=request.POST.get('diagnosis', '').strip() or 'Patient in good health / Normal routine checkup. All good.',
                    treatment_plan=request.POST.get('treatment_plan', '').strip(),
                    clinical_notes=request.POST.get('clinical_notes', '').strip(),
                    follow_up_date=follow_up,
                )

                # Process Dynamic Prescriptions
                med_names = request.POST.getlist('med_name[]')
                dosages = request.POST.getlist('med_dosage[]')
                routes = request.POST.getlist('med_route[]')
                freqs = request.POST.getlist('med_frequency[]')
                durations = request.POST.getlist('med_duration[]')
                instructions = request.POST.getlist('med_instructions[]')

                has_medicines = False
                if target_dest != 'all_good':
                    for i in range(len(med_names)):
                        name = med_names[i].strip()
                        if name:
                            has_medicines = True
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

                if selected_test_ids and target_dest != 'all_good':
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

                    messages.success(request, f"Doctor checkup complete for {patient.full_name}! Lab Order #{lab_order.order_number} created.")
                
                # ------------------------------------------------------------------
                # CLINICAL OPD QUEUE ADVANCEMENT:
                # When checkup is completed, immediately proceed to the NEXT patient in queue!
                # ------------------------------------------------------------------
                next_in_queue = Appointment.objects.filter(
                    clinic=patient.clinic,
                    doctor=doctor,
                    status__in=['WAITING', 'CHECKED_IN']
                ).exclude(pk=appt.pk if appt else 0).select_related('patient', 'doctor').order_by('check_in_time', 'appointment_time', 'id').first()

                if next_in_queue and (target_dest in ['next_patient', 'all_good'] or role == 'DOCTOR'):
                    messages.success(
                        request,
                        f"✓ Checkup complete for {patient.full_name}! Opening NEXT patient in queue: {next_in_queue.patient.full_name} [Token #{next_in_queue.token_number}]."
                    )
                    return redirect(f"/consultations/new/?patient_id={next_in_queue.patient.id}&appointment_id={next_in_queue.id}")

                if target_dest == 'lab':
                    messages.success(request, f"Doctor checkup complete for {patient.full_name}! Lab Order #{lab_order.order_number} created. Proceeding to Laboratory Investigation.")
                    return redirect('laboratory:detail', pk=lab_order.pk)
                elif target_dest == 'pharmacy' or (has_medicines and target_dest not in ['all_good', 'next_patient']):
                    messages.success(request, f"Doctor checkup complete for {patient.full_name}! Prescriptions recorded. Proceeding to Pharmacy for medicine dispensation.")
                    return redirect(f"/pharmacy/dispense/new/?patient_id={patient.pk}&consultation_id={consultation.pk}")
                else:
                    if role == 'DOCTOR':
                        messages.success(request, f"✓ Doctor checkup complete for {patient.full_name}! All patients in your consultation queue are complete.")
                        return redirect('appointments:queue_board')
                    else:
                        messages.success(request, f"Doctor checkup complete! Patient {patient.full_name} is ALL GOOD. Proceeding to Billing & Invoicing.")
                        appt_id_val = appt.id if appt else (appointment_id or '')
                        return redirect(f"/billing/new/?patient_id={patient.pk}&appointment_id={appt_id_val}")

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
        'attending_doctor': attending_doctor,
        'next_waiting_appt': next_waiting_appt,
        'is_doctor_role': role == 'DOCTOR',
    })
