import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from django.test import Client
from apps.patients.models import Patient
from apps.appointments.models import Appointment
from apps.consultations.models import Consultation
from apps.pharmacy.models import MedicineBatch, DispenseRecord
from apps.billing.models import Invoice

print("=====================================================================")
print("TESTING SINGLE LOGIN SESSION (NO LOGOUT / NO MULTIPLE LOGINS)")
print("=====================================================================")

# Testing as Receptionist (Sita Kumari)
c = Client()
res = c.post('/accounts/login/', {'username': 'reception', 'password': 'reception123'}, follow=True)
assert res.status_code == 200, "Receptionist login failed"
print("[✓] Logged in as 'reception' (Sita Kumari)")

# Step 1: Register Patient
res_reg = c.post('/patients/', {
    'first_name': 'Seamless',
    'last_name': 'FlowTest',
    'phone': '+91 9988776655',
    'gender': 'M',
    'blood_group': 'B+'
})
assert res_reg.status_code == 302, "Patient registration should redirect"
patient = Patient.objects.filter(phone='+91 9988776655').first()
assert patient is not None, "Patient was not created"
print(f"[✓ Step 1 Complete] Patient registered: {patient.full_name} -> redirected to {res_reg.url}")

# Step 2: Reception Check-In & Token Generation
res_rec = c.post('/appointments/', {
    'action': 'consult_now',
    'patient': patient.id,
    'doctor': 1,
    'appointment_date': '2026-11-23',
    'appointment_time': '11:00',
    'reason': 'Checkup'
})
assert res_rec.status_code == 302, "Reception checkin should redirect"
appt = Appointment.objects.filter(patient=patient).order_by('-id').first()
assert appt is not None, "Appointment was not created"
print(f"[✓ Step 2 Complete] Token #{appt.token_number} issued -> automatically routed to {res_rec.url}")

# Step 3: Doctor Checkup (Same Session!)
res_checkup = c.get(f"/consultations/new/?patient_id={patient.id}&appointment_id={appt.id}")
assert res_checkup.status_code == 200, f"Doctor Checkup returned {res_checkup.status_code} (Must be 200, NO ACCESS DENIED)"
print("[✓ Step 3 Accessible] Doctor checkup page opened without Access Denied!")

res_doc_post = c.post('/consultations/new/', {
    'patient': patient.id,
    'doctor': 1,
    'appointment_id': appt.id,
    'blood_pressure': '120/80',
    'chief_complaints': 'Fever and body pain',
    'diagnosis': 'Viral Fever',
    'target_destination': 'pharmacy',
    'med_name[]': ['Paracetamol (500mg)'],
    'med_dosage[]': ['1 tablet'],
    'med_route[]': ['Oral'],
    'med_frequency[]': ['1-0-1'],
    'med_duration[]': ['3'],
    'med_instructions[]': ['After food']
})
assert res_doc_post.status_code == 302, "Doctor checkup should redirect"
print(f"[✓ Step 3 Complete] Doctor checkup submitted -> automatically routed to {res_doc_post.url}")

# Step 4: Pharmacy Dispensing (Same Session!)
consultation = Consultation.objects.filter(patient=patient).first()
res_pharma_get = c.get(f"/pharmacy/dispense/new/?patient_id={patient.id}&consultation_id={consultation.id}")
assert res_pharma_get.status_code == 200, f"Pharmacy returned {res_pharma_get.status_code} (Must be 200, NO ACCESS DENIED)"
print("[✓ Step 4 Accessible] Pharmacy dispense page opened without Access Denied!")

batch = MedicineBatch.objects.filter(quantity_in_stock__gt=0).first()
res_pharma_post = c.post('/pharmacy/dispense/new/', {
    'patient': patient.id,
    'consultation': consultation.id,
    'batch[]': [batch.id],
    'quantity[]': [1],
    'price[]': [str(batch.selling_price)],
    'action_next': 'bill'
})
assert res_pharma_post.status_code == 302, "Dispense should redirect"
print(f"[✓ Step 4 Complete] Medicines dispensed -> automatically routed to {res_pharma_post.url}")

# Step 5: Billing & Invoicing (Same Session!)
res_bill_get = c.get(f"/billing/new/?patient_id={patient.id}&appointment_id={appt.id}")
assert res_bill_get.status_code == 200, f"Billing returned {res_bill_get.status_code} (Must be 200, NO ACCESS DENIED)"
print("[✓ Step 5 Accessible] Billing invoice create opened without Access Denied!")

res_bill_post = c.post('/billing/new/', {
    'patient': patient.id,
    'doctor': 1,
    'appointment': appt.id,
    'item_type[]': ['CONSULTATION'],
    'description[]': ['Doctor Consultation Fee'],
    'quantity[]': ['1'],
    'unit_price[]': ['500.00']
})
assert res_bill_post.status_code == 302, "Invoice create should redirect"
invoice = Invoice.objects.filter(patient=patient).order_by('-id').first()
assert invoice is not None, "Invoice not created"
print(f"[✓ Step 5 Complete] Invoice #{invoice.invoice_number} created -> {res_bill_post.url}")

# Record Payment
res_pay = c.post(f"/billing/{invoice.id}/", {
    'action': 'record_payment',
    'amount': str(invoice.total_amount),
    'payment_method': 'CASH',
    'transaction_reference': 'TXN-CASH-001'
})
assert res_pay.status_code == 302
invoice.refresh_from_db()
assert invoice.status == 'PAID', f"Expected PAID, got {invoice.status}"
print(f"[✓ Final Payment Received] Invoice #{invoice.invoice_number} marked PAID in full!")

print("\n=====================================================================")
print(">>> SUCCESS: 100% SINGLE LOGIN SESSION VERIFIED! NO LOGOUT NEEDED! <<<")
print("=====================================================================")
