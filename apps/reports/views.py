from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from decimal import Decimal
from datetime import date, timedelta
from apps.patients.models import Patient
from apps.appointments.models import Appointment
from apps.consultations.models import Consultation
from apps.laboratory.models import LabOrder
from apps.pharmacy.models import Medicine, DispenseRecord
from apps.billing.models import Invoice, Payment
from apps.doctors.models import Doctor

@login_required
def reports_dashboard(request):
    today = date.today()
    this_month = today.replace(day=1)

    is_super = request.user.is_superuser
    profile = getattr(request.user, 'profile', None)
    role = profile.role if profile else ('SUPER_ADMIN' if is_super else 'PATIENT')
    is_admin = is_super or role in ['SUPER_ADMIN', 'CLINIC_ADMIN']

    # 1. Financial Metrics - Restricted to Admins & Accountants only
    if is_admin or role == 'ACCOUNTANT':
        today_collections = Payment.objects.filter(payment_date__date=today).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        month_collections = Payment.objects.filter(payment_date__date__gte=this_month).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_revenue = Payment.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_outstanding = Invoice.objects.filter(status__in=['UNPAID', 'PARTIALLY_PAID']).aggregate(total=Sum('balance_due'))['total'] or Decimal('0.00')
        payment_methods = list(Payment.objects.values('payment_method').annotate(
            count=Count('id'),
            total=Sum('amount')
        ).order_by('-total'))
        pharmacy_revenue = DispenseRecord.objects.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    else:
        # Non-admin users see restricted analytics (no financial data)
        today_collections = None
        month_collections = None
        total_revenue = None
        total_outstanding = None
        payment_methods = []
        pharmacy_revenue = None

    # 2. Clinical Metrics (Accessible for operational analysis)
    total_patients = Patient.objects.count()
    new_patients_month = Patient.objects.filter(created_at__date__gte=this_month).count()
    
    total_appointments = Appointment.objects.count()
    today_appointments = Appointment.objects.filter(appointment_date=today).count()
    completed_appointments = Appointment.objects.filter(status='COMPLETED').count()

    total_consultations = Consultation.objects.count()

    # 3. Doctor-wise consultation stats
    doctor_stats = Doctor.objects.annotate(
        consultation_count=Count('consultations'),
        appointment_count=Count('appointments')
    ).order_by('-consultation_count')

    # 4. Laboratory Metrics
    total_lab_orders = LabOrder.objects.count()
    completed_lab_orders = LabOrder.objects.filter(status='COMPLETED').count()
    pending_lab_orders = LabOrder.objects.filter(status__in=['PENDING', 'SAMPLE_COLLECTED', 'IN_PROCESS']).count()

    # 5. Pharmacy Metrics
    total_medicines = Medicine.objects.count()
    medicines = Medicine.objects.prefetch_related('batches').all()
    low_stock_count = sum(1 for m in medicines if m.is_low_stock)
    total_dispensations = DispenseRecord.objects.count()

    return render(request, 'reports/dashboard.html', {
        'today': today,
        'is_admin': is_admin,
        'can_view_finance': is_admin or role == 'ACCOUNTANT',
        'today_collections': today_collections,
        'month_collections': month_collections,
        'total_revenue': total_revenue,
        'total_outstanding': total_outstanding,
        'payment_methods': payment_methods,
        'total_patients': total_patients,
        'new_patients_month': new_patients_month,
        'total_appointments': total_appointments,
        'today_appointments': today_appointments,
        'completed_appointments': completed_appointments,
        'total_consultations': total_consultations,
        'doctor_stats': doctor_stats,
        'total_lab_orders': total_lab_orders,
        'completed_lab_orders': completed_lab_orders,
        'pending_lab_orders': pending_lab_orders,
        'total_medicines': total_medicines,
        'low_stock_count': low_stock_count,
        'total_dispensations': total_dispensations,
        'pharmacy_revenue': pharmacy_revenue,
    })
