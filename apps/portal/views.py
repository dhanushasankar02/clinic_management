from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import date, datetime, timedelta, time

from apps.clinics.models import Clinic
from apps.patients.models import Patient
from apps.doctors.models import Doctor, Specialty, DoctorAvailability
from apps.appointments.models import Appointment, AppointmentNotification, notify_doctor_appointment
from apps.consultations.models import Consultation
from apps.laboratory.models import LabOrder
from apps.accounts.models import UserProfile, LoginAuditLog, SystemAuditLog


def _get_or_create_patient_for_user(user, clinic=None):
    if not clinic:
        clinic = Clinic.objects.first()
    patient = getattr(user, 'patient_record', None)
    if not patient:
        patient = Patient.objects.filter(user=user).first()
    if not patient:
        if user.email and '@' in user.email:
            patient = Patient.objects.filter(clinic=clinic, email__iexact=user.email, user__isnull=True).first()
        if not patient and hasattr(user, 'profile') and user.profile.phone:
            clean_digits = ''.join(c for c in user.profile.phone if c.isdigit())
            if len(clean_digits) >= 6:
                patient = Patient.objects.filter(clinic=clinic, phone__icontains=clean_digits, user__isnull=True).first()

        if patient:
            patient.user = user
            patient.save(update_fields=['user'])
        else:
            phone_val = getattr(user, 'profile', None).phone if hasattr(user, 'profile') and user.profile.phone else f"90000{user.id:05d}"
            patient = Patient.objects.create(
                clinic=clinic,
                user=user,
                first_name=user.first_name or user.username,
                last_name=user.last_name or '',
                email=user.email or '',
                phone=phone_val,
                gender='M',
                blood_group='UNKNOWN',
            )
    return patient


def get_available_slots(doctor, target_date):
    """Calculates available, unbooked slots for doctor on target_date."""
    today = timezone.localdate()
    if target_date < today:
        return []

    avail = DoctorAvailability.objects.filter(doctor=doctor, available_date=target_date).first()
    if not avail:
        weekday = target_date.weekday()
        avail = DoctorAvailability.objects.filter(doctor=doctor, working_day=weekday).first()

    if avail and (avail.is_leave or not avail.is_available):
        return []

    start_t = avail.start_time if avail else time(9, 0)
    end_t = avail.end_time if avail else time(17, 0)
    slot_mins = avail.slot_duration if avail else 15
    break_s = avail.break_start if avail else time(13, 0)
    break_e = avail.break_end if avail else time(14, 0)

    booked_times = set(
        Appointment.objects.filter(
            doctor=doctor,
            appointment_date=target_date
        ).exclude(
            status__in=['CANCELLED', 'REJECTED']
        ).values_list('appointment_time', flat=True)
    )
    booked_str_times = {t.strftime('%H:%M') for t in booked_times if t}

    slots = []
    current_dt = datetime.combine(target_date, start_t)
    end_dt = datetime.combine(target_date, end_t)
    now = timezone.localtime()

    while current_dt + timedelta(minutes=slot_mins) <= end_dt:
        slot_t = current_dt.time()
        in_break = False
        if break_s and break_e:
            if break_s <= slot_t < break_e:
                in_break = True

        time_str = slot_t.strftime('%H:%M')
        is_past = False
        if target_date == today and current_dt <= now.replace(tzinfo=None):
            is_past = True

        if not in_break and not is_past and time_str not in booked_str_times:
            slots.append(time_str)

        current_dt += timedelta(minutes=slot_mins)

    return slots


# ================= 1. PATIENT REGISTRATION & AUTHENTICATION =================

def portal_register(request):
    clinic = Clinic.objects.first()
    if request.user.is_authenticated:
        return redirect('portal:dashboard')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        dob_str = request.POST.get('date_of_birth', '').strip()
        gender = request.POST.get('gender', 'M')
        address = request.POST.get('address', '').strip()
        blood_group = request.POST.get('blood_group', '').strip()
        allergies = request.POST.get('allergies', '').strip()
        chronic_conditions = request.POST.get('chronic_conditions', '').strip()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        if not (first_name and phone and username and password):
            messages.error(request, "Please fill in all mandatory fields (Name, Phone, Username, Password).")
        elif password != confirm_password:
            messages.error(request, "Passwords do not match. Please verify your password.")
        elif len(password) < 6:
            messages.error(request, "Password must be at least 6 characters long.")
        elif User.objects.filter(username=username).exists():
            messages.error(request, f"Username '{username}' is already taken. Please choose another username.")
        elif Patient.objects.filter(clinic=clinic, phone=phone).exists():
            messages.error(request, f"A patient profile with phone '{phone}' is already registered. Please sign in or use another number.")
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_staff=False,
                is_superuser=False,
            )
            UserProfile.objects.create(
                user=user,
                clinic=clinic,
                role='PATIENT',
                phone=phone
            )
            dob = None
            if dob_str:
                try:
                    dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
                except Exception:
                    pass

            patient = Patient.objects.create(
                clinic=clinic,
                user=user,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                email=email,
                date_of_birth=dob,
                gender=gender,
                blood_group=blood_group,
                allergies=allergies,
                chronic_conditions=chronic_conditions,
                address=address,
            )

            # Record login session
            login(request, user)
            if not request.session.session_key:
                request.session.save()
            
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
            LoginAuditLog.objects.create(
                user=user,
                username_attempted=user.username,
                email=user.email,
                role='Patient',
                session_key=request.session.session_key,
                ip_address=ip,
                status='ACTIVE'
            )

            AppointmentNotification.objects.create(
                user=user,
                message=f"Welcome to {clinic.name} Patient Portal! Your Patient MRN ID is {patient.patient_id}.",
                notification_type='WELCOME'
            )

            messages.success(request, f"Welcome {patient.full_name}! Your account has been registered with ID {patient.patient_id}.")
            return redirect('portal:dashboard')

    return render(request, 'portal/register.html', {'clinic': clinic})


def portal_login(request):
    if request.user.is_authenticated:
        return redirect('portal:dashboard')
    return redirect('accounts:login')


@login_required
def portal_logout(request):
    name = request.user.get_full_name() or request.user.username
    if request.session.session_key:
        LoginAuditLog.objects.filter(
            user=request.user,
            session_key=request.session.session_key,
            status='ACTIVE'
        ).update(status='LOGGED_OUT', logout_time=timezone.now())
    logout(request)
    messages.info(request, f"Goodbye {name}! You have been logged out securely.")
    return redirect('accounts:login')


# ================= 2. PATIENT DASHBOARD =================

@login_required
def portal_dashboard(request):
    clinic = Clinic.objects.first()
    patient = _get_or_create_patient_for_user(request.user, clinic)
    today = timezone.localdate()

    upcoming_appointments = Appointment.objects.filter(
        patient=patient,
        appointment_date__gte=today
    ).exclude(
        status__in=['CANCELLED', 'REJECTED', 'COMPLETED']
    ).select_related('doctor', 'department').order_by('appointment_date', 'appointment_time')

    next_appointment = upcoming_appointments.first()
    total_appointments = Appointment.objects.filter(patient=patient).count()
    total_consultations = Consultation.objects.filter(patient=patient).count()
    total_lab_orders = LabOrder.objects.filter(patient=patient).count()
    unread_notifications = AppointmentNotification.objects.filter(user=request.user, is_read=False).count()

    recent_consultations = Consultation.objects.filter(patient=patient).select_related('doctor').order_by('-created_at')[:4]

    return render(request, 'portal/dashboard.html', {
        'clinic': clinic,
        'patient': patient,
        'next_appointment': next_appointment,
        'upcoming_appointments': upcoming_appointments[:5],
        'total_appointments': total_appointments,
        'total_consultations': total_consultations,
        'total_lab_orders': total_lab_orders,
        'unread_notifications': unread_notifications,
        'recent_consultations': recent_consultations,
    })


# ================= 3. MY PROFILE =================

@login_required
def portal_profile(request):
    clinic = Clinic.objects.first()
    patient = _get_or_create_patient_for_user(request.user, clinic)

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        gender = request.POST.get('gender', '').strip()
        dob_str = request.POST.get('date_of_birth', '').strip()
        blood_group = request.POST.get('blood_group', '').strip()
        address = request.POST.get('address', '').strip()
        allergies = request.POST.get('allergies', '').strip()
        chronic = request.POST.get('chronic_conditions', '').strip()
        emergency_name = request.POST.get('emergency_contact_name', '').strip()
        emergency_phone = request.POST.get('emergency_contact_phone', '').strip()

        if first_name:
            patient.first_name = first_name
            request.user.first_name = first_name
        if last_name:
            patient.last_name = last_name
            request.user.last_name = last_name
        if phone:
            patient.phone = phone
            if hasattr(request.user, 'profile'):
                request.user.profile.phone = phone
                request.user.profile.save()
        if email:
            patient.email = email
            request.user.email = email
        if gender:
            patient.gender = gender
        if blood_group:
            patient.blood_group = blood_group
        if allergies is not None:
            patient.allergies = allergies
        if chronic is not None:
            patient.chronic_conditions = chronic
        if dob_str:
            try:
                patient.date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date()
            except Exception:
                pass
        patient.address = address
        patient.emergency_contact_name = emergency_name
        patient.emergency_contact_phone = emergency_phone
        patient.save()
        request.user.save()

        messages.success(request, "Your profile details have been updated successfully.")
        return redirect('portal:profile')

    return render(request, 'portal/profile.html', {
        'clinic': clinic,
        'patient': patient,
    })


# ================= 4. BOOK APPOINTMENT =================

@login_required
def portal_book_appointment(request):
    clinic = Clinic.objects.first()
    patient = _get_or_create_patient_for_user(request.user, clinic)
    today = timezone.localdate()

    specialties = Specialty.objects.all()
    doctors = Doctor.objects.filter(clinic=clinic, is_available=True).select_related('specialty')

    if request.method == 'POST':
        doctor_id = request.POST.get('doctor')
        appt_date_str = request.POST.get('appointment_date')
        appt_time_str = request.POST.get('appointment_time')
        appt_type = request.POST.get('appointment_type', 'NEW')
        reason = request.POST.get('reason', '').strip()
        notes = request.POST.get('notes', '').strip()

        if not (doctor_id and appt_date_str and appt_time_str and reason):
            messages.error(request, "Please fill in all required appointment details (Doctor, Date, Time, and Reason for visit).")
        else:
            try:
                appt_date = datetime.strptime(appt_date_str, '%Y-%m-%d').date()
            except ValueError:
                appt_date = None

            if not appt_date or appt_date < today:
                messages.error(request, "Appointment date cannot be in the past. Please select today or a future date.")
            else:
                doctor = get_object_or_404(Doctor, pk=doctor_id, clinic=clinic)
                
                # Check backend slot availability to prevent double-booking
                available_slots = get_available_slots(doctor, appt_date)
                formatted_time = appt_time_str[:5]

                # Check if doctor is already booked at this exact time
                is_already_booked = Appointment.objects.filter(
                    doctor=doctor,
                    appointment_date=appt_date,
                    appointment_time=appt_time_str
                ).exclude(status__in=['CANCELLED', 'REJECTED']).exists()

                if is_already_booked:
                    messages.error(request, f"Sorry, the time slot {formatted_time} on {appt_date} is already booked. Please choose another available time.")
                else:
                    appointment = Appointment.objects.create(
                        clinic=clinic,
                        patient=patient,
                        doctor=doctor,
                        department=doctor.specialty,
                        appointment_date=appt_date,
                        appointment_time=appt_time_str,
                        appointment_type=appt_type,
                        status='PENDING',
                        source='ONLINE',
                        reason=reason,
                        notes=notes,
                    )

                    # Create Patient Notification
                    AppointmentNotification.objects.create(
                        user=request.user,
                        appointment=appointment,
                        message=f"Appointment #{appointment.appointment_id} booked with Dr. {doctor.name} for {appt_date} at {formatted_time}. Status: Pending Confirmation.",
                        notification_type='BOOKED'
                    )

                    # Create Doctor Notification (ONLY for the assigned doctor)
                    notify_doctor_appointment(appointment, event_type='BOOKED')

                    # Log to system audit
                    SystemAuditLog.objects.create(
                        user=request.user,
                        action='ONLINE_APPOINTMENT_BOOKED',
                        module='Appointments',
                        details=f"Patient {patient.full_name} booked #{appointment.appointment_id} with Dr. {doctor.name} for {appt_date} at {formatted_time}."
                    )

                    messages.success(request, f"Your appointment #{appointment.appointment_id} with Dr. {doctor.name} has been booked! Our reception team will review and confirm your slot.")
                    return redirect('portal:my_appointments')

    return render(request, 'portal/book_appointment.html', {
        'clinic': clinic,
        'patient': patient,
        'specialties': specialties,
        'doctors': doctors,
        'today': today.isoformat(),
    })


def api_available_slots(request):
    """AJAX endpoint for returning available time slots for doctor and date."""
    doctor_id = request.GET.get('doctor_id')
    date_str = request.GET.get('date')

    if not (doctor_id and date_str):
        return JsonResponse({'error': 'doctor_id and date parameters are required.'}, status=400)

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        doctor = Doctor.objects.get(pk=doctor_id)
    except (ValueError, Doctor.DoesNotExist):
        return JsonResponse({'error': 'Invalid doctor or date.'}, status=400)

    slots = get_available_slots(doctor, target_date)
    return JsonResponse({
        'doctor_id': doctor.id,
        'doctor_name': doctor.name,
        'date': date_str,
        'slots': slots,
        'total_available': len(slots),
        'available': len(slots) > 0,
    })


# ================= 5. MY APPOINTMENTS & HISTORY =================

@login_required
def portal_appointments(request):
    clinic = Clinic.objects.first()
    patient = _get_or_create_patient_for_user(request.user, clinic)
    today = timezone.localdate()

    appointments = Appointment.objects.filter(
        patient=patient
    ).exclude(
        status__in=['COMPLETED', 'CANCELLED', 'REJECTED']
    ).select_related('doctor', 'department').order_by('appointment_date', 'appointment_time')

    return render(request, 'portal/my_appointments.html', {
        'clinic': clinic,
        'patient': patient,
        'appointments': appointments,
    })


@login_required
def portal_appointment_history(request):
    clinic = Clinic.objects.first()
    patient = _get_or_create_patient_for_user(request.user, clinic)

    appointments = Appointment.objects.filter(
        patient=patient,
        status__in=['COMPLETED', 'CANCELLED', 'REJECTED']
    ).select_related('doctor', 'department').order_by('-appointment_date', '-appointment_time')

    return render(request, 'portal/appointment_history.html', {
        'clinic': clinic,
        'patient': patient,
        'appointments': appointments,
    })


@login_required
def portal_cancel_appointment(request, pk):
    clinic = Clinic.objects.first()
    patient = _get_or_create_patient_for_user(request.user, clinic)
    appointment = get_object_or_404(Appointment, pk=pk, patient=patient)

    if appointment.status in ['COMPLETED', 'CANCELLED', 'REJECTED']:
        messages.error(request, f"This appointment is already {appointment.get_status_display().lower()} and cannot be cancelled.")
    else:
        appointment.status = 'CANCELLED'
        appointment.cancellation_reason = request.POST.get('reason', 'Cancelled by patient via online portal.')
        appointment.save()

        AppointmentNotification.objects.create(
            user=request.user,
            appointment=appointment,
            message=f"Your appointment #{appointment.appointment_id} with Dr. {appointment.doctor.name} on {appointment.appointment_date} has been cancelled.",
            notification_type='CANCELLED'
        )

        # Notify only the assigned doctor
        notify_doctor_appointment(appointment, event_type='CANCELLED')

        messages.success(request, f"Appointment #{appointment.appointment_id} has been cancelled successfully.")

    return redirect('portal:my_appointments')


# ================= 6. MY PRESCRIPTIONS =================

@login_required
def portal_prescriptions(request):
    clinic = Clinic.objects.first()
    patient = _get_or_create_patient_for_user(request.user, clinic)

    consultations = Consultation.objects.filter(
        patient=patient
    ).prefetch_related('prescriptions').select_related('doctor').order_by('-created_at')

    return render(request, 'portal/prescriptions.html', {
        'clinic': clinic,
        'patient': patient,
        'consultations': consultations,
    })


@login_required
def portal_prescription_detail(request, pk):
    clinic = Clinic.objects.first()
    patient = _get_or_create_patient_for_user(request.user, clinic)
    consultation = get_object_or_404(Consultation.objects.prefetch_related('prescriptions').select_related('doctor', 'patient'), pk=pk, patient=patient)

    return render(request, 'portal/prescription_detail.html', {
        'clinic': clinic,
        'patient': patient,
        'consultation': consultation,
    })


# ================= 7. MY LABORATORY REPORTS =================

@login_required
def portal_lab_reports(request):
    clinic = Clinic.objects.first()
    patient = _get_or_create_patient_for_user(request.user, clinic)

    lab_orders = LabOrder.objects.filter(
        patient=patient
    ).prefetch_related('items__test').select_related('doctor').order_by('-created_at')

    return render(request, 'portal/lab_reports.html', {
        'clinic': clinic,
        'patient': patient,
        'lab_orders': lab_orders,
    })


@login_required
def portal_lab_report_detail(request, pk):
    clinic = Clinic.objects.first()
    patient = _get_or_create_patient_for_user(request.user, clinic)
    lab_order = get_object_or_404(LabOrder.objects.prefetch_related('items__test').select_related('doctor', 'patient', 'clinic'), pk=pk, patient=patient)

    return render(request, 'portal/lab_report_detail.html', {
        'clinic': clinic,
        'patient': patient,
        'order': lab_order,
    })


# ================= 8. MY MEDICAL RECORDS (EMR) =================

@login_required
def portal_medical_records(request):
    clinic = Clinic.objects.first()
    patient = _get_or_create_patient_for_user(request.user, clinic)

    consultations = patient.consultations.select_related('doctor').prefetch_related('prescriptions').order_by('-created_at')
    lab_orders = patient.lab_orders.select_related('doctor').prefetch_related('items__test').order_by('-created_at')
    appointments = patient.appointments.select_related('doctor', 'department').order_by('-appointment_date', '-appointment_time')

    return render(request, 'portal/medical_records.html', {
        'clinic': clinic,
        'patient': patient,
        'consultations': consultations,
        'lab_orders': lab_orders,
        'appointments': appointments,
    })


# ================= 9. NOTIFICATIONS =================

@login_required
def portal_notifications(request):
    notifications = AppointmentNotification.objects.filter(user=request.user).select_related('appointment').order_by('-created_at')
    # Mark all read on visit
    AppointmentNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)

    return render(request, 'portal/notifications.html', {
        'notifications': notifications,
    })


@login_required
def portal_notification_read(request, pk):
    notification = get_object_or_404(AppointmentNotification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save()
    return redirect('portal:notifications')


# ================= 10. CHANGE PASSWORD =================

@login_required
def portal_change_password(request):
    if request.method == 'POST':
        old_password = request.POST.get('old_password', '').strip()
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        if not request.user.check_password(old_password):
            messages.error(request, "Incorrect current password. Please try again.")
        elif len(new_password) < 6:
            messages.error(request, "New password must be at least 6 characters long.")
        elif new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
        else:
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)

            messages.success(request, "Your password has been changed successfully!")
            return redirect('portal:dashboard')

    return render(request, 'portal/change_password.html')
