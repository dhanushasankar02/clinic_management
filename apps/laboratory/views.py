from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from rest_framework import viewsets
from apps.laboratory.models import LabTest, LabOrder, LabOrderItem
from apps.laboratory.serializers import LabTestSerializer, LabOrderSerializer
from apps.patients.models import Patient
from apps.doctors.models import Doctor
from apps.accounts.decorators import role_required

# REST API ViewSets
class LabTestViewSet(viewsets.ModelViewSet):
    queryset = LabTest.objects.all()
    serializer_class = LabTestSerializer


class LabOrderViewSet(viewsets.ModelViewSet):
    queryset = LabOrder.objects.all().prefetch_related('items__test', 'patient', 'doctor')
    serializer_class = LabOrderSerializer


# Frontend Views
@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'LAB_TECH', 'DOCTOR', 'NURSE'])
def order_list(request):
    status_filter = request.GET.get('status', '')
    orders = LabOrder.objects.select_related('patient', 'doctor').prefetch_related('items__test').all()
    if status_filter:
        orders = orders.filter(status=status_filter)

    counts = {
        'total': LabOrder.objects.count(),
        'pending': LabOrder.objects.filter(status='PENDING').count(),
        'collected': LabOrder.objects.filter(status='SAMPLE_COLLECTED').count(),
        'in_process': LabOrder.objects.filter(status='IN_PROCESS').count(),
        'completed': LabOrder.objects.filter(status='COMPLETED').count(),
    }

    return render(request, 'laboratory/order_list.html', {
        'orders': orders,
        'status_filter': status_filter,
        'counts': counts,
    })


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'LAB_TECH', 'DOCTOR', 'NURSE', 'RECEPTIONIST'])
def order_detail(request, pk):
    order = get_object_or_404(LabOrder.objects.select_related('patient', 'doctor', 'clinic').prefetch_related('items__test'), pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_status':
            new_status = request.POST.get('status')
            order.status = new_status
            order.save()
            messages.success(request, f"Order status updated to {order.get_status_display()}.")
        elif action == 'save_results':
            for item in order.items.all():
                val_key = f"result_{item.id}"
                flag_key = f"flag_{item.id}"
                remarks_key = f"remarks_{item.id}"
                if val_key in request.POST:
                    item.result_value = request.POST.get(val_key, '').strip()
                    item.flag = request.POST.get(flag_key, 'NORMAL')
                    item.technician_remarks = request.POST.get(remarks_key, '').strip()
                    item.tested_at = timezone.now()
                    item.is_verified = True
                    item.verified_by = request.POST.get('verified_by', 'Lab Supervisor')
                    item.save()
            
            # If all items have results, set order status to completed
            if all(i.result_value for i in order.items.all()):
                order.status = 'COMPLETED'
                order.save()
            messages.success(request, "Lab investigation results recorded and verified successfully.")

            next_dest = request.POST.get('next_action', '')
            if next_dest == 'pharmacy':
                messages.success(request, f"Proceeding to Pharmacy for {order.patient.full_name}'s medication dispensing.")
                consult_param = f"&consultation_id={order.consultation.pk}" if order.consultation else ""
                return redirect(f"/pharmacy/dispense/new/?patient_id={order.patient.pk}{consult_param}")

        return redirect('laboratory:detail', pk=order.pk)

    return render(request, 'laboratory/order_detail.html', {
        'order': order,
    })


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'LAB_TECH', 'DOCTOR', 'NURSE', 'RECEPTIONIST'])
def order_create(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient')
        doctor_id = request.POST.get('doctor') or None
        priority = request.POST.get('priority', 'ROUTINE')
        notes = request.POST.get('clinical_notes', '').strip()
        test_ids = request.POST.getlist('tests[]')

        if not patient_id or not test_ids:
            messages.error(request, "Please select both a patient and at least one lab test.")
        else:
            patient = get_object_or_404(Patient, pk=patient_id)
            doctor = Doctor.objects.filter(pk=doctor_id).first() if doctor_id else None
            order = LabOrder.objects.create(
                clinic=patient.clinic,
                patient=patient,
                doctor=doctor,
                priority=priority,
                status='PENDING',
                clinical_notes=notes
            )
            for tid in test_ids:
                t = LabTest.objects.filter(pk=tid).first()
                if t:
                    LabOrderItem.objects.create(order=order, test=t)
            messages.success(request, f"Lab Order #{order.order_number} created successfully.")
            return redirect('laboratory:detail', pk=order.pk)

    patients = Patient.objects.all()
    doctors = Doctor.objects.all()
    tests = LabTest.objects.filter(is_active=True)
    return render(request, 'laboratory/order_create.html', {
        'patients': patients,
        'doctors': doctors,
        'tests': tests,
    })


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'LAB_TECH', 'DOCTOR', 'NURSE', 'RECEPTIONIST'])
def order_print_report(request, pk):
    order = get_object_or_404(LabOrder.objects.select_related('patient', 'doctor', 'clinic').prefetch_related('items__test'), pk=pk)
    return render(request, 'laboratory/print_report.html', {
        'order': order,
        'clinic': order.clinic,
    })


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'LAB_TECH', 'DOCTOR', 'NURSE'])
def test_catalogue(request):
    tests = LabTest.objects.all()
    return render(request, 'laboratory/catalogue.html', {
        'tests': tests,
    })
