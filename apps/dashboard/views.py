from django.shortcuts import render, redirect
from django.db.models import Sum, Q
from datetime import date
from decimal import Decimal
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from apps.clinics.models import Clinic
from apps.doctors.models import Doctor
from apps.patients.models import Patient
from apps.appointments.models import Appointment, AppointmentNotification
from apps.consultations.models import Consultation
from apps.laboratory.models import LabOrder
from apps.pharmacy.models import Medicine, MedicineBatch, DispenseRecord
from apps.billing.models import Payment, Invoice
from apps.communication.models import WhatsAppConversation, WhatsAppMessage
from apps.accounts.models import LoginAuditLog, UserProfile
from apps.accounts.views import get_login_stats
from apps.accounts.decorators import role_required, admin_required


def _get_admin_dashboard_context(request):
    clinic = Clinic.objects.first()
    today = date.today()
    this_month = today.replace(day=1)

    today_appointments = Appointment.objects.filter(
        clinic=clinic,
        appointment_date=today
    ).select_related('doctor', 'patient')

    today_payments = round(Decimal(str(Payment.objects.filter(payment_date__date=today).aggregate(tot=Sum('amount'))['tot'] or '0.00')), 2)
    month_payments = round(Decimal(str(Payment.objects.filter(payment_date__date__gte=this_month).aggregate(tot=Sum('amount'))['tot'] or '0.00')), 2)
    lifetime_revenue = round(Decimal(str(Payment.objects.aggregate(tot=Sum('amount'))['tot'] or '0.00')), 2)
    total_outstanding = round(Decimal(str(Invoice.objects.filter(status__in=['UNPAID', 'PARTIALLY_PAID']).aggregate(tot=Sum('balance_due'))['tot'] or '0.00')), 2)

    medicines = Medicine.objects.prefetch_related('batches').all()
    low_stock_count = sum(1 for m in medicines if m.is_low_stock)

    login_stats = get_login_stats()
    recent_login_logs = LoginAuditLog.objects.select_related('user').all()[:6]

    stats = {
        'total_patients': Patient.objects.filter(clinic=clinic).count() if clinic else 0,
        'today_appointments_count': today_appointments.count(),
        'waiting_queue_count': today_appointments.filter(status__in=['WAITING', 'CHECKED_IN', 'IN_CONSULTATION']).count(),
        'completed_today': today_appointments.filter(status='COMPLETED').count(),
        'total_doctors': Doctor.objects.filter(clinic=clinic, is_available=True).count() if clinic else 0,
        'today_revenue': today_payments,
        'month_revenue': month_payments,
        'lifetime_revenue': lifetime_revenue,
        'total_outstanding': total_outstanding,
        'total_invoices_count': Invoice.objects.count(),
        'staff_users_count': login_stats['total_registered_users'],
        'distinct_logged_in_count': login_stats['currently_logged_in_users'],
        'pending_lab_count': LabOrder.objects.filter(status__in=['PENDING', 'SAMPLE_COLLECTED', 'IN_PROCESS']).count(),
        'low_stock_count': low_stock_count,
        'total_consultations': Consultation.objects.count(),
        'active_conversations': WhatsAppConversation.objects.filter(clinic=clinic).count() if clinic else 0,
    }

    recent_appointments = Appointment.objects.filter(clinic=clinic).select_related('doctor', 'patient')[:6]
    recent_consultations = Consultation.objects.select_related('doctor', 'patient').order_by('-created_at')[:5]
    doctors = Doctor.objects.filter(clinic=clinic).select_related('specialty')[:4]
    recent_messages = WhatsAppMessage.objects.filter(conversation__clinic=clinic).select_related('conversation')[:5]

    return {
        'clinic': clinic,
        'stats': stats,
        'today_appointments': today_appointments,
        'recent_appointments': recent_appointments,
        'recent_consultations': recent_consultations,
        'doctors': doctors,
        'recent_messages': recent_messages,
        'today': today,
        'can_view_finance': True,
        'total_members_count': login_stats['total_registered_users'],
        'distinct_logged_in_count': login_stats['currently_logged_in_users'],
        'recent_login_logs': recent_login_logs,
        'login_stats': login_stats,
    }


def dashboard_index(request):
    if not request.user.is_authenticated:
        return redirect('accounts:login')

    is_super = request.user.is_superuser
    profile = getattr(request.user, 'profile', None)
    role = profile.role if profile else ('SUPER_ADMIN' if is_super else 'CLINIC_ADMIN')

    if role == 'PATIENT':
        return redirect('portal:dashboard')

    # If Admin, show Executive Admin Dashboard
    if is_super or role in ['SUPER_ADMIN', 'CLINIC_ADMIN']:
        return render(request, 'dashboard/index.html', _get_admin_dashboard_context(request))

    # Route ordinary staff directly to their specific role dashboard
    if role == 'DOCTOR':
        return redirect('dashboard:doctor')
    elif role == 'RECEPTIONIST':
        return redirect('dashboard:receptionist')
    elif role == 'NURSE':
        return redirect('dashboard:nurse')
    elif role == 'LAB_TECH':
        return redirect('dashboard:lab')
    elif role == 'PHARMACIST':
        return redirect('dashboard:pharmacist')
    elif role == 'ACCOUNTANT':
        return redirect('dashboard:accountant')
    elif role == 'INVENTORY_MGR':
        return redirect('dashboard:inventory')

    return redirect('accounts:login')


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'DOCTOR'])
def doctor_dashboard(request):
    clinic = Clinic.objects.first()
    today = date.today()

    # Identify the specific doctor profile if logged in as a doctor
    current_doctor = getattr(request.user, 'doctor_profile', None)
    if not current_doctor and request.user.is_authenticated:
        current_doctor = Doctor.objects.filter(user=request.user).first()

    today_appointments = Appointment.objects.filter(
        clinic=clinic,
        appointment_date=today
    ).select_related('doctor', 'patient').order_by('token_number')

    # Filter to ONLY this doctor's appointments
    if current_doctor:
        today_appointments = today_appointments.filter(doctor=current_doctor)

    waiting_queue = today_appointments.filter(status__in=['WAITING', 'CHECKED_IN'])
    in_consult = today_appointments.filter(status='IN_CONSULTATION').first()
    completed_today = today_appointments.filter(status='COMPLETED').count()

    recent_consultations = Consultation.objects.select_related('doctor', 'patient').order_by('-created_at')
    if current_doctor:
        recent_consultations = recent_consultations.filter(doctor=current_doctor)
    recent_consultations = recent_consultations[:8]

    pending_lab_orders = LabOrder.objects.filter(status__in=['PENDING', 'SAMPLE_COLLECTED'])
    if current_doctor:
        pending_lab_orders = pending_lab_orders.filter(doctor=current_doctor)
    pending_lab_orders = pending_lab_orders.count()

    # Doctor's personal appointment notifications (ONLY for this doctor)
    doctor_notifications = AppointmentNotification.objects.filter(user=request.user).select_related('appointment').order_by('-created_at')[:8]
    unread_notifications_count = AppointmentNotification.objects.filter(user=request.user, is_read=False).count()

    return render(request, 'dashboard/doctor.html', {
        'clinic': clinic,
        'today': today,
        'current_doctor': current_doctor,
        'today_appointments': today_appointments,
        'waiting_queue': waiting_queue,
        'in_consult': in_consult,
        'completed_today': completed_today,
        'recent_consultations': recent_consultations,
        'pending_lab_orders': pending_lab_orders,
        'doctor_notifications': doctor_notifications,
        'unread_notifications_count': unread_notifications_count,
    })


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'RECEPTIONIST'])
def receptionist_dashboard(request):
    clinic = Clinic.objects.first()
    today = date.today()

    today_appointments = Appointment.objects.filter(
        clinic=clinic,
        appointment_date=today
    ).select_related('doctor', 'patient').order_by('token_number')

    waiting_queue = today_appointments.filter(status__in=['WAITING', 'CHECKED_IN'])
    total_booked = today_appointments.count()
    completed_count = today_appointments.filter(status='COMPLETED').count()
    checked_in_count = today_appointments.filter(status__in=['CHECKED_IN', 'IN_CONSULTATION', 'COMPLETED']).count()

    recent_patients = Patient.objects.filter(clinic=clinic).order_by('-created_at')[:6]

    return render(request, 'dashboard/receptionist.html', {
        'clinic': clinic,
        'today': today,
        'today_appointments': today_appointments,
        'waiting_queue': waiting_queue,
        'total_booked': total_booked,
        'completed_count': completed_count,
        'checked_in_count': checked_in_count,
        'recent_patients': recent_patients,
    })


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'NURSE'])
def nurse_dashboard(request):
    clinic = Clinic.objects.first()
    today = date.today()

    today_appointments = Appointment.objects.filter(
        clinic=clinic,
        appointment_date=today
    ).select_related('doctor', 'patient').order_by('token_number')

    vitals_pending = today_appointments.filter(status__in=['WAITING', 'CHECKED_IN'])
    recent_consultations = Consultation.objects.filter(created_at__date=today).select_related('patient', 'doctor')[:6]

    return render(request, 'dashboard/nurse.html', {
        'clinic': clinic,
        'today': today,
        'today_appointments': today_appointments,
        'vitals_pending': vitals_pending,
        'recent_consultations': recent_consultations,
    })


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'LAB_TECH'])
def lab_dashboard(request):
    clinic = Clinic.objects.first()
    today = date.today()

    pending_orders = LabOrder.objects.filter(status='PENDING').select_related('patient', 'doctor').prefetch_related('items__test')
    collected_orders = LabOrder.objects.filter(status='SAMPLE_COLLECTED').select_related('patient', 'doctor').prefetch_related('items__test')
    in_process_orders = LabOrder.objects.filter(status='IN_PROCESS').select_related('patient', 'doctor').prefetch_related('items__test')
    completed_today = LabOrder.objects.filter(status='COMPLETED', updated_at__date=today).count()

    return render(request, 'dashboard/lab.html', {
        'clinic': clinic,
        'today': today,
        'pending_orders': pending_orders,
        'collected_orders': collected_orders,
        'in_process_orders': in_process_orders,
        'completed_today': completed_today,
    })


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'PHARMACIST'])
def pharmacist_dashboard(request):
    clinic = Clinic.objects.first()
    today = date.today()

    medicines = Medicine.objects.prefetch_related('batches').all()
    low_stock = [m for m in medicines if m.is_low_stock]

    today_dispensations = DispenseRecord.objects.filter(created_at__date=today).select_related('patient').prefetch_related('items__batch__medicine')[:8]
    total_dispensed_today = DispenseRecord.objects.filter(created_at__date=today).count()

    return render(request, 'dashboard/pharmacist.html', {
        'clinic': clinic,
        'today': today,
        'low_stock_medicines': low_stock,
        'low_stock_count': len(low_stock),
        'today_dispensations': today_dispensations,
        'total_dispensed_today': total_dispensed_today,
        'total_medicines': medicines.count(),
    })


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'ACCOUNTANT'])
def accountant_dashboard(request):
    clinic = Clinic.objects.first()
    today = date.today()
    this_month = today.replace(day=1)

    today_payments = Payment.objects.filter(payment_date__date=today)
    today_revenue = today_payments.aggregate(tot=Sum('amount'))['tot'] or Decimal('0.00')
    month_revenue = Payment.objects.filter(payment_date__date__gte=this_month).aggregate(tot=Sum('amount'))['tot'] or Decimal('0.00')

    unpaid_invoices = Invoice.objects.filter(status__in=['UNPAID', 'PARTIALLY_PAID']).select_related('patient')[:10]
    total_outstanding = Invoice.objects.filter(status__in=['UNPAID', 'PARTIALLY_PAID']).aggregate(tot=Sum('balance_due'))['tot'] or Decimal('0.00')

    recent_payments = Payment.objects.select_related('invoice__patient').order_by('-payment_date')[:8]

    return render(request, 'dashboard/accountant.html', {
        'clinic': clinic,
        'today': today,
        'today_revenue': today_revenue,
        'month_revenue': month_revenue,
        'total_outstanding': total_outstanding,
        'unpaid_invoices': unpaid_invoices,
        'recent_payments': recent_payments,
    })


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'INVENTORY_MGR'])
def inventory_dashboard(request):
    clinic = Clinic.objects.first()
    medicines = Medicine.objects.prefetch_related('batches').all()
    low_stock = [m for m in medicines if m.is_low_stock]

    recent_batches = MedicineBatch.objects.select_related('medicine').order_by('-created_at')[:8]

    return render(request, 'dashboard/inventory.html', {
        'clinic': clinic,
        'medicines': medicines,
        'low_stock_medicines': low_stock,
        'low_stock_count': len(low_stock),
        'total_medicines': medicines.count(),
        'recent_batches': recent_batches,
    })


@login_required
def my_assigned_tasks(request):
    """Staff view: My Assigned Tasks based on user's role."""
    clinic = Clinic.objects.first()
    today = date.today()
    profile = getattr(request.user, 'profile', None)
    role = profile.role if profile else ('SUPER_ADMIN' if request.user.is_superuser else 'STAFF')

    tasks = []

    if role in ['SUPER_ADMIN', 'CLINIC_ADMIN']:
        low_count = sum(1 for m in Medicine.objects.prefetch_related('batches').all() if m.is_low_stock)
        tasks = [
            {'title': 'Review Staff & User Accounts', 'desc': 'Audit active staff and assign roles.', 'link': '/accounts/users/', 'badge': 'Admin', 'color': 'teal'},
            {'title': 'Review Login Activity Logs', 'desc': 'Check active login sessions and failed attempts.', 'link': '/accounts/login-activity/', 'badge': 'Security', 'color': 'indigo'},
            {'title': 'Check Low Stock Medicines', 'desc': f'{low_count} items requiring re-order.', 'link': '/pharmacy/', 'badge': 'Pharmacy', 'color': 'rose'},
            {'title': 'Outstanding Patient Invoices', 'desc': 'Follow up on unpaid clinic bills.', 'link': '/billing/', 'badge': 'Finance', 'color': 'amber'},
        ]
    elif role == 'DOCTOR':
        current_doctor = getattr(request.user, 'doctor_profile', None)
        if not current_doctor:
            current_doctor = Doctor.objects.filter(user=request.user).first()
        today_appts = Appointment.objects.filter(clinic=clinic, appointment_date=today, status__in=['WAITING', 'CHECKED_IN'])
        if current_doctor:
            today_appts = today_appts.filter(doctor=current_doctor)
        for a in today_appts:
            tasks.append({
                'title': f"Consultation with {a.patient.full_name} (Token #{a.token_number})",
                'desc': f"Scheduled for {a.appointment_time} - {a.reason_for_visit or 'General Consultation'}",
                'link': f"/consultations/new/?appointment_id={a.id}",
                'badge': 'Pending Consult',
                'color': 'emerald'
            })
    elif role == 'RECEPTIONIST':
        waiting = Appointment.objects.filter(clinic=clinic, appointment_date=today, status='WAITING')
        for a in waiting:
            tasks.append({
                'title': f"Check-in {a.patient.full_name} (Token #{a.token_number})",
                'desc': f"Doctor: {a.doctor.full_name if a.doctor else 'Unassigned'} at {a.appointment_time}",
                'link': '/appointments/queue/',
                'badge': 'Check-In Due',
                'color': 'amber'
            })
    elif role == 'NURSE':
        waiting = Appointment.objects.filter(clinic=clinic, appointment_date=today, status__in=['WAITING', 'CHECKED_IN'])
        for a in waiting:
            tasks.append({
                'title': f"Record Vitals: {a.patient.full_name} (Token #{a.token_number})",
                'desc': f"Triage vitals recording before consultation",
                'link': '/appointments/queue/',
                'badge': 'Vitals Due',
                'color': 'pink'
            })
    elif role == 'LAB_TECH':
        orders = LabOrder.objects.filter(status__in=['PENDING', 'SAMPLE_COLLECTED', 'IN_PROCESS'])
        for o in orders:
            tasks.append({
                'title': f"Lab Order #{o.order_number}: {o.test.name}",
                'desc': f"Patient: {o.patient.full_name} | Status: {o.get_status_display()}",
                'link': f"/laboratory/orders/{o.id}/",
                'badge': o.get_status_display(),
                'color': 'indigo'
            })
    elif role == 'PHARMACIST':
        meds = [m for m in Medicine.objects.prefetch_related('batches').all() if m.is_low_stock]
        for m in meds:
            tasks.append({
                'title': f"Reorder Stock: {m.name}",
                'desc': f"Current stock: {m.total_stock} (Below reorder level: {m.reorder_level})",
                'link': f"/pharmacy/medicines/{m.id}/batch/add/",
                'badge': 'Low Stock',
                'color': 'rose'
            })
    elif role == 'ACCOUNTANT':
        unpaid = Invoice.objects.filter(status__in=['UNPAID', 'PARTIALLY_PAID'])[:10]
        for inv in unpaid:
            tasks.append({
                'title': f"Collect Invoice #{inv.invoice_number} - ₹{inv.balance_due}",
                'desc': f"Patient: {inv.patient.full_name} | Due Date: {inv.due_date}",
                'link': f"/billing/{inv.id}/",
                'badge': inv.get_status_display(),
                'color': 'cyan'
            })
    elif role == 'INVENTORY_MGR':
        meds = [m for m in Medicine.objects.prefetch_related('batches').all() if m.is_low_stock]
        for m in meds:
            tasks.append({
                'title': f"Procure Medicine Batch: {m.name}",
                'desc': f"Stock at {m.total_stock} units. Restock required.",
                'link': f"/pharmacy/medicines/{m.id}/batch/add/",
                'badge': 'Procurement Alert',
                'color': 'blue'
            })

    return render(request, 'dashboard/tasks.html', {
        'tasks': tasks,
        'role_display': profile.get_role_display() if profile else 'Staff',
    })
