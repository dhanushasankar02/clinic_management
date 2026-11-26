from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from decimal import Decimal
from rest_framework import viewsets
from apps.billing.models import Service, Invoice, InvoiceItem, Payment
from apps.billing.serializers import ServiceSerializer, InvoiceSerializer, PaymentSerializer
from apps.patients.models import Patient
from apps.doctors.models import Doctor
from apps.appointments.models import Appointment
from apps.accounts.decorators import get_dashboard_url_for_user

# REST API ViewSets
class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all().select_related('patient', 'doctor').prefetch_related('items', 'payments')
    serializer_class = InvoiceSerializer


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all().select_related('invoice')
    serializer_class = PaymentSerializer


# Frontend Views
@login_required
def invoice_list(request):
    is_super = request.user.is_superuser
    profile = getattr(request.user, 'profile', None)
    role = profile.role if profile else ('SUPER_ADMIN' if is_super else 'STAFF')
    is_admin = is_super or role in ['SUPER_ADMIN', 'CLINIC_ADMIN']
    can_manage_billing = is_admin or role in ['ACCOUNTANT', 'RECEPTIONIST', 'DOCTOR', 'PHARMACIST', 'NURSE', 'LAB_TECH']

    if not can_manage_billing:
        messages.error(request, "Access restricted: Financial records and invoices are restricted to Clinic Staff.")
        return redirect('dashboard:index')

    status_filter = request.GET.get('status', '')
    invoices = Invoice.objects.select_related('patient', 'doctor').all()
    if status_filter:
        invoices = invoices.filter(status=status_filter)

    total_billed = sum((inv.total_amount for inv in invoices), Decimal('0.00'))
    total_collected = sum((inv.paid_amount for inv in invoices), Decimal('0.00'))
    total_outstanding = sum((inv.balance_due for inv in invoices), Decimal('0.00'))

    return render(request, 'billing/invoice_list.html', {
        'invoices': invoices,
        'status_filter': status_filter,
        'total_billed': total_billed,
        'total_collected': total_collected,
        'total_outstanding': total_outstanding,
        'can_manage_billing': can_manage_billing,
    })


@login_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related('patient', 'doctor', 'clinic').prefetch_related('items', 'payments'), pk=pk)

    is_super = request.user.is_superuser or request.user.is_staff
    profile = getattr(request.user, 'profile', None)
    role = profile.role if profile else ('SUPER_ADMIN' if is_super else 'STAFF')
    can_record_payment = is_super or role in ['SUPER_ADMIN', 'CLINIC_ADMIN', 'ACCOUNTANT', 'RECEPTIONIST', 'DOCTOR', 'PHARMACIST']

    if request.method == 'POST':
        if not can_record_payment:
            messages.error(request, "Permission denied: Only Accounting and Reception staff can record payments.")
            return redirect('billing:invoice_detail', pk=invoice.pk)

        action = request.POST.get('action')
        if action == 'record_payment':
            amount = request.POST.get('amount')
            method = request.POST.get('payment_method', 'CASH')
            txn_ref = request.POST.get('transaction_reference', '').strip()
            notes = request.POST.get('notes', '').strip()

            if amount:
                pay_amt = Decimal(amount)
                if pay_amt > 0:
                    Payment.objects.create(
                        invoice=invoice,
                        amount=pay_amt,
                        payment_method=method,
                        transaction_reference=txn_ref,
                        received_by=request.user.get_full_name() or request.user.username,
                        notes=notes
                    )
                    messages.success(request, f"Payment of ₹{pay_amt} recorded successfully!")
                    return redirect('billing:invoice_detail', pk=invoice.pk)
                else:
                    messages.error(request, "Payment amount must be greater than zero.")
            else:
                messages.error(request, "Please enter payment amount.")

    return render(request, 'billing/invoice_detail.html', {
        'invoice': invoice,
        'can_record_payment': can_record_payment,
    })


@login_required
def invoice_create(request):
    is_super = request.user.is_superuser
    profile = getattr(request.user, 'profile', None)
    role = profile.role if profile else ('SUPER_ADMIN' if is_super else 'STAFF')
    is_admin = is_super or role in ['SUPER_ADMIN', 'CLINIC_ADMIN']

    # Full invoice creation desk is available to Billing/Accounting/Admin/Reception staff.
    # Clinical staff (Doctors, Pharmacists, Nurses, Lab Techs) can seamlessly generate invoices during patient encounters (when patient_id or appointment_id or POST patient is provided).
    has_patient_context = bool(request.GET.get('patient_id') or request.GET.get('appointment_id') or request.POST.get('patient'))
    can_create = is_admin or role in ['ACCOUNTANT', 'RECEPTIONIST'] or (has_patient_context and role in ['DOCTOR', 'PHARMACIST', 'NURSE', 'LAB_TECH'])

    if not can_create:
        messages.info(request, "To create an invoice, please select a patient from patient records or appointment encounters.")
        return redirect(get_dashboard_url_for_user(request.user))

    patients = Patient.objects.all()
    doctors = Doctor.objects.all()
    services = Service.objects.filter(is_active=True)

    patient_id = request.GET.get('patient_id')
    appointment_id = request.GET.get('appointment_id')
    appointment = Appointment.objects.filter(pk=appointment_id).select_related('doctor', 'patient').first() if appointment_id else None

    selected_patient = None
    selected_doctor = None
    if appointment:
        selected_patient = appointment.patient
        selected_doctor = appointment.doctor
    elif patient_id:
        selected_patient = Patient.objects.filter(pk=patient_id).first()

    if request.method == 'POST':
        p_id = request.POST.get('patient')
        d_id = request.POST.get('doctor') or None
        appt_pk = request.POST.get('appointment')
        discount = request.POST.get('discount', '0.00')
        tax_pct = request.POST.get('tax_percent', '0.00')
        due_date = request.POST.get('due_date') or None
        notes = request.POST.get('notes', '').strip()

        item_types = request.POST.getlist('item_type[]')
        descriptions = request.POST.getlist('description[]')
        quantities = request.POST.getlist('quantity[]')
        unit_prices = request.POST.getlist('unit_price[]')

        if not p_id or not descriptions:
            messages.error(request, "Please choose a patient and add at least one line item.")
        else:
            try:
                with transaction.atomic():
                    patient = get_object_or_404(Patient, pk=p_id)
                    doctor = Doctor.objects.filter(pk=d_id).first() if d_id else None
                    appt_obj = Appointment.objects.filter(pk=appt_pk).first() if appt_pk else None
                    consult_obj = getattr(appt_obj, 'consultation', None) if appt_obj else None

                    invoice = Invoice.objects.create(
                        clinic=patient.clinic,
                        patient=patient,
                        doctor=doctor,
                        appointment=appt_obj,
                        consultation=consult_obj,
                        discount=Decimal(discount or '0.00'),
                        tax_percent=Decimal(tax_pct or '0.00'),
                        due_date=due_date,
                        notes=notes
                    )

                    for i in range(len(descriptions)):
                        desc = descriptions[i].strip()
                        if desc:
                            itype = item_types[i] if i < len(item_types) else 'CONSULTATION'
                            qty = int(quantities[i]) if i < len(quantities) and quantities[i].isdigit() else 1
                            price = Decimal(unit_prices[i]) if i < len(unit_prices) else Decimal('0.00')
                            InvoiceItem.objects.create(
                                invoice=invoice,
                                item_type=itype,
                                description=desc,
                                quantity=qty,
                                unit_price=price
                            )

                    invoice.recalculate()
                    messages.success(request, f"Invoice #{invoice.invoice_number} created successfully! Total: ₹{invoice.total_amount}")
                    return redirect('billing:invoice_detail', pk=invoice.pk)
            except Exception as e:
                messages.error(request, f"Failed to create invoice: {str(e)}")

    return render(request, 'billing/invoice_create.html', {
        'patients': patients,
        'doctors': doctors,
        'services': services,
        'selected_patient': selected_patient,
        'selected_doctor': selected_doctor,
        'appointment': appointment,
    })


@login_required
def invoice_print(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related('patient', 'doctor', 'clinic').prefetch_related('items', 'payments'), pk=pk)
    return render(request, 'billing/print_invoice.html', {
        'invoice': invoice,
        'clinic': invoice.clinic,
    })


@login_required
def service_catalogue(request):
    is_super = request.user.is_superuser
    profile = getattr(request.user, 'profile', None)
    role = profile.role if profile else ('SUPER_ADMIN' if is_super else 'STAFF')
    is_admin = is_super or role in ['SUPER_ADMIN', 'CLINIC_ADMIN']
    if not (is_admin or role in ['ACCOUNTANT', 'RECEPTIONIST', 'DOCTOR', 'PHARMACIST', 'NURSE', 'LAB_TECH']):
        messages.error(request, "Access restricted: Service tariff catalogue is restricted.")
        return redirect('dashboard:index')

    services = Service.objects.all()
    return render(request, 'billing/services.html', {'services': services})
