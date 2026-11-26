from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from decimal import Decimal
from datetime import date, timedelta
from rest_framework import viewsets
from apps.pharmacy.models import Medicine, MedicineBatch, DispenseRecord, DispenseItem
from apps.pharmacy.serializers import MedicineSerializer, DispenseRecordSerializer
from apps.patients.models import Patient
from apps.consultations.models import Consultation
from apps.billing.models import Invoice, InvoiceItem
from apps.accounts.decorators import role_required
from django.db import models

# REST API
class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all().prefetch_related('batches')
    serializer_class = MedicineSerializer


class DispenseRecordViewSet(viewsets.ModelViewSet):
    queryset = DispenseRecord.objects.all().prefetch_related('items__batch__medicine')
    serializer_class = DispenseRecordSerializer


# Frontend Views
@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'PHARMACIST', 'INVENTORY_MGR', 'DOCTOR', 'RECEPTIONIST', 'NURSE', 'LAB_TECH', 'ACCOUNTANT'])
def pharmacy_dashboard(request):
    medicines = Medicine.objects.prefetch_related('batches').all()
    today = date.today()
    near_cutoff = today + timedelta(days=60)

    low_stock_items = [m for m in medicines if m.is_low_stock]
    near_expiry_batches = MedicineBatch.objects.select_related('medicine').filter(
        expiry_date__gte=today,
        expiry_date__lte=near_cutoff,
        quantity_in_stock__gt=0
    )
    recent_dispensations = DispenseRecord.objects.select_related('patient').order_by('-created_at')[:10]

    return render(request, 'pharmacy/dashboard.html', {
        'total_medicines': len(medicines),
        'low_stock_items': low_stock_items,
        'near_expiry_batches': near_expiry_batches,
        'recent_dispensations': recent_dispensations,
    })


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'PHARMACIST', 'INVENTORY_MGR', 'DOCTOR', 'RECEPTIONIST', 'NURSE', 'LAB_TECH', 'ACCOUNTANT'])
def medicine_list(request):
    query = request.GET.get('q', '').strip()
    medicines = Medicine.objects.prefetch_related('batches').all()
    if query:
        medicines = medicines.filter(
            models.Q(name__icontains=query) |
            models.Q(generic_name__icontains=query) |
            models.Q(category__icontains=query)
        )
    return render(request, 'pharmacy/medicine_list.html', {
        'medicines': medicines,
        'query': query,
    })


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'PHARMACIST', 'INVENTORY_MGR'])
def batch_add(request, medicine_id=None):
    medicines = Medicine.objects.filter(is_active=True)
    selected_medicine_id = medicine_id or request.GET.get('medicine')
    if request.method == 'POST':
        med_id = request.POST.get('medicine')
        batch_no = request.POST.get('batch_number', '').strip()
        expiry = request.POST.get('expiry_date')
        qty = request.POST.get('quantity_in_stock', '0')
        pur_price = request.POST.get('purchase_price', '0')
        sell_price = request.POST.get('selling_price', '0')
        supplier = request.POST.get('supplier', '').strip()

        if med_id and batch_no and expiry:
            med = get_object_or_404(Medicine, pk=med_id)
            MedicineBatch.objects.create(
                medicine=med,
                batch_number=batch_no,
                expiry_date=expiry,
                quantity_in_stock=int(qty),
                purchase_price=Decimal(pur_price),
                selling_price=Decimal(sell_price),
                supplier=supplier
            )
            messages.success(request, f"Batch {batch_no} added successfully for {med.name}!")
            return redirect('pharmacy:medicine_list')
        else:
            messages.error(request, "Please fill in all mandatory batch details.")

    return render(request, 'pharmacy/batch_add.html', {'medicines': medicines})


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'PHARMACIST', 'RECEPTIONIST', 'DOCTOR', 'NURSE'])
def dispense_create(request):
    patients = Patient.objects.all()
    batches = MedicineBatch.objects.select_related('medicine').filter(
        quantity_in_stock__gt=0,
        expiry_date__gte=date.today()
    )

    consultation_id = request.GET.get('consultation_id') or request.POST.get('consultation')
    consultation = None
    if consultation_id:
        consultation = Consultation.objects.filter(pk=consultation_id).select_related('patient', 'doctor').prefetch_related('prescriptions').first()

    patient_id_param = request.GET.get('patient_id')
    selected_patient = None
    if consultation:
        selected_patient = consultation.patient
    elif patient_id_param:
        selected_patient = Patient.objects.filter(pk=patient_id_param).first()

    if request.method == 'POST':
        patient_id = request.POST.get('patient')
        batch_ids = request.POST.getlist('batch[]')
        quantities = request.POST.getlist('quantity[]')
        prices = request.POST.getlist('price[]')
        notes = request.POST.get('notes', '').strip()
        consult_pk = request.POST.get('consultation')
        consult_obj = Consultation.objects.filter(pk=consult_pk).first() if consult_pk else None

        if not patient_id or not batch_ids:
            messages.error(request, "Please select a patient and at least one medicine batch.")
        else:
            try:
                with transaction.atomic():
                    patient = get_object_or_404(Patient, pk=patient_id)
                    dispense = DispenseRecord.objects.create(
                        clinic=patient.clinic,
                        patient=patient,
                        consultation=consult_obj,
                        dispensed_by="Pharmacy Staff",
                        notes=notes
                    )
                    total = Decimal('0.00')
                    for i in range(len(batch_ids)):
                        if i < len(quantities) and int(quantities[i]) > 0:
                            b = get_object_or_404(MedicineBatch, pk=batch_ids[i])
                            q = int(quantities[i])
                            u_price = Decimal(prices[i]) if i < len(prices) else b.selling_price
                            item = DispenseItem.objects.create(
                                dispense=dispense,
                                batch=b,
                                quantity=q,
                                unit_price=u_price,
                                total_price=q * u_price
                            )
                            total += item.total_price

                    dispense.total_amount = total
                    dispense.save()
                    messages.success(request, f"Dispensation #{dispense.dispense_number} completed. Total: ₹{total}")

                    action_next = request.POST.get('action_next', '')
                    if action_next == 'bill':
                        appt_pk = consult_obj.appointment.pk if (consult_obj and consult_obj.appointment) else ''
                        messages.success(request, f"Prescription dispensed! Proceeding directly to Final Billing & Invoicing for {patient.full_name}.")
                        return redirect(f"/billing/new/?patient_id={patient.pk}{'&appointment_id=' + str(appt_pk) if appt_pk else ''}")

                    return redirect('pharmacy:dispense_detail', pk=dispense.pk)
            except Exception as e:
                messages.error(request, f"Failed to dispense: {str(e)}")

    return render(request, 'pharmacy/dispense_create.html', {
        'patients': patients,
        'batches': batches,
        'consultation': consultation,
        'selected_patient': selected_patient,
    })


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'PHARMACIST', 'INVENTORY_MGR', 'RECEPTIONIST', 'DOCTOR', 'NURSE', 'LAB_TECH', 'ACCOUNTANT'])
def dispense_detail(request, pk):
    dispense = get_object_or_404(DispenseRecord.objects.select_related('patient', 'clinic').prefetch_related('items__batch__medicine'), pk=pk)
    return render(request, 'pharmacy/dispense_detail.html', {
        'dispense': dispense,
        'clinic': dispense.clinic,
    })


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'PHARMACIST', 'INVENTORY_MGR', 'DOCTOR', 'RECEPTIONIST', 'NURSE', 'LAB_TECH', 'ACCOUNTANT'])
def dispense_list(request):
    dispensations = DispenseRecord.objects.select_related('patient').prefetch_related('items__batch__medicine').order_by('-created_at')
    return render(request, 'pharmacy/dispense_list.html', {'dispensations': dispensations})
