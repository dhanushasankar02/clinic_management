from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from rest_framework import viewsets
from datetime import date
import random
from apps.appointments.models import Appointment, AppointmentNotification, notify_doctor_appointment
from apps.appointments.serializers import AppointmentSerializer
from apps.doctors.models import Doctor, Specialty, DoctorAvailability
from apps.patients.models import Patient
from apps.clinics.models import Clinic
from apps.accounts.decorators import role_required

@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'DOCTOR', 'RECEPTIONIST', 'NURSE', 'PHARMACIST', 'LAB_TECH', 'ACCOUNTANT'])
def appointment_list(request):
    clinic = Clinic.objects.first()
    status_filter = request.GET.get('status', '')
    doctor_filter = request.GET.get('doctor', '')
    date_filter = request.GET.get('date', '')
    patient_id_param = request.GET.get('patient_id')
    new_patient_param = request.GET.get('new_patient') == '1'
    selected_patient = Patient.objects.filter(id=patient_id_param, clinic=clinic).first() if patient_id_param else None

    profile = getattr(request.user, 'profile', None)
    role = profile.role if profile else None
    current_doctor = getattr(request.user, 'doctor_profile', None) or Doctor.objects.filter(user=request.user).first()

    # If logged in as Doctor and no specific doctor filter passed (and not explicitly requesting all), default to current doctor's appointments
    if role == 'DOCTOR' and current_doctor and not doctor_filter and request.GET.get('all') != '1':
        doctor_filter = str(current_doctor.id)

    appointments = Appointment.objects.filter(clinic=clinic).select_related('doctor', 'patient', 'doctor__specialty', 'consultation').prefetch_related('invoices')

    if status_filter:
        appointments = appointments.filter(status=status_filter)
    if doctor_filter:
        appointments = appointments.filter(doctor_id=doctor_filter)
    if date_filter:
        appointments = appointments.filter(appointment_date=date_filter)

    doctors = Doctor.objects.filter(clinic=clinic, is_available=True)
    patients = Patient.objects.filter(clinic=clinic)

    if request.method == 'POST':
        action = request.POST.get('action', 'book')
        doctor_id = request.POST.get('doctor')
        patient_id = request.POST.get('patient')
        patient_name = request.POST.get('patient_name', '').strip()
        patient_phone = request.POST.get('patient_phone', '').strip()
        patient_email = request.POST.get('patient_email', '').strip()
        patient_gender = request.POST.get('gender', 'M')
        patient_blood_group = request.POST.get('blood_group', 'UNKNOWN')
        patient_allergies = request.POST.get('allergies', '').strip()
        patient_address = request.POST.get('address', '').strip()
        appt_date = request.POST.get('appointment_date')
        appt_time = request.POST.get('appointment_time')
        reason = request.POST.get('reason', 'Consultation').strip()
        is_walk_in = request.POST.get('is_walk_in') == 'true' or action in ['consult_now', 'book_and_queue']

        if not doctor_id:
            messages.error(request, 'Please select a doctor.')
            return redirect('appointments:list')

        if not appt_date or not appt_time:
            messages.error(request, 'Please specify an appointment date and time.')
            return redirect('appointments:list')

        doc = get_object_or_404(Doctor, id=doctor_id, clinic=clinic)

        # Resolve or create patient
        pat = None
        if patient_id:
            pat = Patient.objects.filter(id=patient_id, clinic=clinic).first()

        if not pat and patient_name:
            if not patient_phone:
                patient_phone = f"+91 {random.randint(9100000000, 9999999999)}"

            name_parts = patient_name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''

            pat, created = Patient.objects.get_or_create(
                clinic=clinic,
                phone=patient_phone,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': patient_email,
                    'gender': patient_gender,
                    'blood_group': patient_blood_group,
                    'allergies': patient_allergies,
                    'address': patient_address
                }
            )

        if not pat:
            messages.error(request, 'Please enter a patient name or select an existing patient.')
            return redirect('appointments:list')

        # Prevent duplicate appointment booking on the same date and time
        from django.db.models import Q
        existing_appt = Appointment.objects.filter(
            clinic=clinic,
            appointment_date=appt_date,
            appointment_time=appt_time
        ).filter(Q(doctor=doc) | Q(patient=pat)).exclude(status='CANCELLED').first()

        if existing_appt:
            if existing_appt.doctor_id == doc.id and existing_appt.patient_id == pat.id:
                messages.warning(request, f"An appointment already exists for {pat.full_name} with Dr. {doc.name} on {appt_date} at {appt_time} (Token: {existing_appt.token_number}). Duplicate booking prevented.")
            elif existing_appt.doctor_id == doc.id:
                messages.warning(request, f"Dr. {doc.name} already has an appointment scheduled on {appt_date} at {appt_time}. Please pick another time slot.")
            else:
                messages.warning(request, f"{pat.full_name} already has an appointment booked on {appt_date} at {appt_time}.")
            return redirect('appointments:list')

        # Create appointment
        if action == 'consult_now':
            status = 'IN_CONSULTATION'
            source = 'WALK_IN'
            checkin = timezone.now()
        elif action == 'book_and_queue' or is_walk_in:
            status = 'WAITING'
            source = 'WALK_IN'
            checkin = timezone.now()
        else:
            status = 'CONFIRMED'
            source = 'WEB'
            checkin = None

        appt = Appointment.objects.create(
            clinic=clinic,
            doctor=doc,
            patient=pat,
            appointment_date=appt_date,
            appointment_time=appt_time,
            status=status,
            source=source,
            check_in_time=checkin,
            reason=reason or 'General Consultation'
        )

        # Notify only the assigned doctor
        notify_doctor_appointment(appt, event_type='BOOKED')

        if action == 'consult_now':
            messages.success(request, f'Token #{appt.token_number} generated at Reception! Proceeding directly to Doctor Checkup for {pat.full_name}.')
            return redirect(f"/consultations/new/?patient_id={pat.id}&appointment_id={appt.id}")
        elif action == 'book_and_queue':
            messages.success(request, f'Reception check-in complete! Token #{appt.token_number} issued for {pat.full_name}. In queue for Doctor Checkup.')
            return redirect('appointments:queue_board')
        else:
            messages.success(request, f'Appointment successfully booked for {pat.full_name} with Dr. {doc.name}. Token: {appt.token_number}')
            return redirect('appointments:list')

    profile = getattr(request.user, 'profile', None)
    role = profile.role if profile else ('SUPER_ADMIN' if request.user.is_superuser else 'STAFF')
    can_view_billing = request.user.is_superuser or role in ['SUPER_ADMIN', 'CLINIC_ADMIN', 'ACCOUNTANT', 'RECEPTIONIST']

    return render(request, 'appointments/list.html', {
        'appointments': appointments,
        'doctors': doctors,
        'patients': patients,
        'status_filter': status_filter,
        'doctor_filter': doctor_filter,
        'date_filter': date_filter,
        'today': date.today().isoformat(),
        'clinic': clinic,
        'selected_patient': selected_patient,
        'is_new_patient': new_patient_param,
        'can_view_billing': can_view_billing,
        'current_doctor': current_doctor,
    })


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'RECEPTIONIST', 'DOCTOR', 'NURSE', 'PHARMACIST', 'LAB_TECH', 'ACCOUNTANT'])
def queue_board(request):
    clinic = Clinic.objects.first()
    today = date.today()
    today_appts = Appointment.objects.filter(clinic=clinic, appointment_date=today).select_related('doctor', 'patient')

    profile = getattr(request.user, 'profile', None)
    role = profile.role if profile else ('SUPER_ADMIN' if request.user.is_superuser else 'STAFF')
    current_doctor = getattr(request.user, 'doctor_profile', None) or Doctor.objects.filter(user=request.user).first()
    doctor_filter = request.GET.get('doctor', '')

    # If logged in as Doctor, automatically show ONLY appointments booked for this doctor
    if role == 'DOCTOR' and current_doctor:
        today_appts = today_appts.filter(doctor=current_doctor)
    elif doctor_filter:
        today_appts = today_appts.filter(doctor_id=doctor_filter)

    waiting_queue = today_appts.filter(status__in=['CHECKED_IN', 'WAITING']).order_by('check_in_time', 'appointment_time')
    in_consultation = today_appts.filter(status='IN_CONSULTATION')
    completed_today = today_appts.filter(status='COMPLETED').order_by('-updated_at')[:10]

    can_view_billing = request.user.is_superuser or role in ['SUPER_ADMIN', 'CLINIC_ADMIN', 'ACCOUNTANT', 'RECEPTIONIST']

    return render(request, 'appointments/queue.html', {
        'waiting_queue': waiting_queue,
        'in_consultation': in_consultation,
        'completed_today': completed_today,
        'today': today,
        'clinic': clinic,
        'can_view_billing': can_view_billing,
        'current_doctor': current_doctor if role == 'DOCTOR' else None,
    })


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'RECEPTIONIST', 'NURSE', 'DOCTOR'])
def check_in_patient(request, pk):
    clinic = Clinic.objects.first()
    appt = get_object_or_404(Appointment, pk=pk, clinic=clinic)
    appt.status = 'WAITING'
    appt.check_in_time = timezone.now()
    appt.save()
    messages.success(request, f"Patient {appt.patient.full_name} checked-in! Token: {appt.token_number}")
    return redirect('appointments:queue_board')


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'DOCTOR', 'RECEPTIONIST', 'NURSE'])
def appointment_status_update(request, pk):
    clinic = Clinic.objects.first()
    appt = get_object_or_404(Appointment, pk=pk, clinic=clinic)
    new_status = request.POST.get('status') or request.GET.get('status')
    if new_status in dict(Appointment.STATUS_CHOICES):
        appt.status = new_status
        if new_status in ['CHECKED_IN', 'WAITING'] and not appt.check_in_time:
            appt.check_in_time = timezone.now()
        appt.save()
        messages.success(request, f'Appointment status updated to {appt.get_status_display()}.')
    return redirect('appointments:list')


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'RECEPTIONIST', 'DOCTOR', 'NURSE'])
def print_visit_slip(request, pk):
    clinic = Clinic.objects.first()
    appt = get_object_or_404(Appointment.objects.select_related('doctor', 'patient', 'clinic'), pk=pk, clinic=clinic)
    return render(request, 'appointments/visit_slip.html', {
        'appointment': appt,
        'clinic': clinic or appt.clinic,
    })


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'RECEPTIONIST', 'DOCTOR'])
def appointment_confirm(request, pk):
    clinic = Clinic.objects.first()
    appt = get_object_or_404(Appointment, pk=pk, clinic=clinic)
    appt.status = 'CONFIRMED'
    appt.save()

    if appt.patient.user:
        AppointmentNotification.objects.create(
            user=appt.patient.user,
            appointment=appt,
            message=f"Good news! Your appointment #{appt.appointment_id} with Dr. {appt.doctor.name} on {appt.appointment_date} at {appt.appointment_time} has been CONFIRMED.",
            notification_type='CONFIRMED'
        )

    # Notify only the assigned doctor
    notify_doctor_appointment(appt, event_type='CONFIRMED')

    messages.success(request, f"Appointment #{appt.appointment_id} for {appt.patient.full_name} has been CONFIRMED.")
    return redirect('appointments:list')


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'RECEPTIONIST', 'DOCTOR'])
def appointment_reject(request, pk):
    clinic = Clinic.objects.first()
    appt = get_object_or_404(Appointment, pk=pk, clinic=clinic)
    reason = request.POST.get('reason', 'Doctor unavailable or scheduling conflict.').strip()
    appt.status = 'REJECTED'
    appt.cancellation_reason = reason
    appt.save()

    if appt.patient.user:
        AppointmentNotification.objects.create(
            user=appt.patient.user,
            appointment=appt,
            message=f"Your appointment #{appt.appointment_id} with Dr. {appt.doctor.name} for {appt.appointment_date} was rejected. Reason: {reason}",
            notification_type='REJECTED'
        )

    # Notify only the assigned doctor
    notify_doctor_appointment(appt, event_type='REJECTED')

    messages.info(request, f"Appointment #{appt.appointment_id} has been marked as REJECTED.")
    return redirect('appointments:list')


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'RECEPTIONIST', 'DOCTOR'])
def appointment_reschedule(request, pk):
    clinic = Clinic.objects.first()
    appt = get_object_or_404(Appointment, pk=pk, clinic=clinic)

    if request.method == 'POST':
        new_date = request.POST.get('appointment_date')
        new_time = request.POST.get('appointment_time')
        if new_date and new_time:
            appt.appointment_date = new_date
            appt.appointment_time = new_time
            appt.status = 'CONFIRMED'
            appt.save()

            if appt.patient.user:
                AppointmentNotification.objects.create(
                    user=appt.patient.user,
                    appointment=appt,
                    message=f"Your appointment #{appt.appointment_id} with Dr. {appt.doctor.name} has been rescheduled to {new_date} at {new_time}.",
                    notification_type='RESCHEDULED'
                )

            # Notify only the assigned doctor
            notify_doctor_appointment(appt, event_type='RESCHEDULED')

            messages.success(request, f"Appointment #{appt.appointment_id} rescheduled to {new_date} at {new_time}.")
        else:
            messages.error(request, "Please provide valid new date and time.")

    return redirect('appointments:list')


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'RECEPTIONIST', 'DOCTOR'])
def appointment_cancel(request, pk):
    clinic = Clinic.objects.first()
    appt = get_object_or_404(Appointment, pk=pk, clinic=clinic)
    appt.status = 'CANCELLED'
    appt.cancellation_reason = request.POST.get('reason', 'Cancelled by clinic staff.').strip()
    appt.save()

    if appt.patient.user:
        AppointmentNotification.objects.create(
            user=appt.patient.user,
            appointment=appt,
            message=f"Your appointment #{appt.appointment_id} with Dr. {appt.doctor.name} on {appt.appointment_date} has been cancelled by clinic administration.",
            notification_type='CANCELLED'
        )

    # Notify only the assigned doctor
    notify_doctor_appointment(appt, event_type='CANCELLED')

    messages.info(request, f"Appointment #{appt.appointment_id} has been cancelled.")
    return redirect('appointments:list')


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'DOCTOR', 'RECEPTIONIST', 'NURSE'])
def doctor_availability_list(request):
    clinic = Clinic.objects.first()
    doctors = Doctor.objects.filter(clinic=clinic).prefetch_related('availabilities')

    if request.method == 'POST':
        is_super = request.user.is_superuser
        profile = getattr(request.user, 'profile', None)
        if not (is_super or (profile and profile.role in ['SUPER_ADMIN', 'CLINIC_ADMIN'])):
            messages.error(request, "Access restricted: Only Clinic Administrators can modify doctor availability schedules.")
            return redirect('appointments:availability')

        doc_id = request.POST.get('doctor')
        day_of_week = request.POST.get('working_day')
        start_t = request.POST.get('start_time', '09:00')
        end_t = request.POST.get('end_time', '17:00')
        slot_mins = int(request.POST.get('slot_duration', 15))
        is_leave = 'is_leave' in request.POST
        is_avail = not is_leave

        if doc_id and day_of_week is not None:
            doc = get_object_or_404(Doctor, pk=doc_id)
            avail, _ = DoctorAvailability.objects.update_or_create(
                doctor=doc,
                working_day=int(day_of_week),
                defaults={
                    'start_time': start_t,
                    'end_time': end_t,
                    'slot_duration': slot_mins,
                    'is_available': is_avail,
                    'is_leave': is_leave,
                }
            )
            messages.success(request, f"Availability schedule updated for Dr. {doc.name}.")
            return redirect('appointments:availability')

    availabilities = DoctorAvailability.objects.select_related('doctor').order_by('doctor', 'working_day')
    return render(request, 'appointments/availability.html', {
        'clinic': clinic,
        'doctors': doctors,
        'availabilities': availabilities,
        'days': DoctorAvailability._meta.get_field('working_day').choices,
    })


class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all().select_related('doctor', 'patient')
    serializer_class = AppointmentSerializer
