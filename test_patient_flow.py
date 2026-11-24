import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from django.test import Client
from apps.clinics.models import Clinic
from apps.patients.models import Patient
from apps.doctors.models import Doctor
from apps.appointments.models import Appointment
from apps.consultations.models import Consultation
from apps.laboratory.models import LabTest, LabOrder
from apps.pharmacy.models import Medicine, MedicineBatch, DispenseRecord

def test_full_patient_flow():
    print("=====================================================================")
    print("TESTING FULL PATIENT ORDER WORKFLOW (SRS & USER SPECIFICATION)")
    print("Order: Register -> Reception Enter -> Doctor Checkup -> Lab/Pharmacy")
    print("=====================================================================")

    client = Client()
    # Log in as admin (has full role permissions)
    login_res = client.get('/accounts/login/?demo=admin', follow=True)
    assert login_res.status_code == 200, "Admin login failed"

    clinic = Clinic.objects.first()
    doctor = Doctor.objects.first()
    assert clinic and doctor, "Clinic and Doctor must exist"

    # -------------------------------------------------------------
    # STAGE 1: PATIENT REGISTRATION -> NEXT GO TO RECEPTION ENTER
    # -------------------------------------------------------------
    print("\n[Stage 1] Registering New Patient...")
    reg_phone = "+91 9888877771"
    # Ensure cleanup if exists from previous run
    Patient.objects.filter(phone=reg_phone).delete()

    reg_data = {
        'first_name': 'Dev',
        'last_name': 'Kalyan',
        'phone': reg_phone,
        'email': 'dev.kalyan@example.com',
        'gender': 'M',
        'blood_group': 'B+',
        'allergies': 'Sulfa drugs',
        'medical_notes': 'Mild hypertension',
        'address': 'Koramangala, Bangalore'
    }

    res_reg = client.post('/patients/', data=reg_data, follow=False)
    assert res_reg.status_code == 302, f"Expected 302 redirect from patient registration, got {res_reg.status_code}"
    
    patient = Patient.objects.filter(phone=reg_phone).first()
    assert patient is not None, "Patient was not created in database"

    expected_redirect = f"/appointments/?patient_id={patient.id}&new_patient=1"
    assert res_reg['Location'] == expected_redirect, f"Expected redirect to {expected_redirect}, got {res_reg['Location']}"
    print(f" -> [PASS] Patient registered: {patient.full_name} ({patient.patient_id})")
    print(f" -> [PASS] Automatically redirected to Reception: {res_reg['Location']}")

    # Check that Reception Desk page renders with patient pre-selected
    res_appt_page = client.get(res_reg['Location'])
    assert res_appt_page.status_code == 200
    assert patient.full_name in res_appt_page.content.decode('utf-8')
    print(" -> [PASS] Reception desk loaded with patient pre-selected")

    # -------------------------------------------------------------
    # STAGE 2: RECEPTION ENTER & REGISTER APPOINTMENT / TOKEN
    # -------------------------------------------------------------
    print("\n[Stage 2] Reception Enter & Register (Token generation)...")
    appt_data = {
        'doctor': doctor.id,
        'patient': patient.id,
        'appointment_date': '2026-11-25',
        'appointment_time': '11:00',
        'reason': 'Chest discomfort and seasonal fever',
        'action': 'consult_now'  # Register & Proceed to Doctor Checkup
    }

    res_appt = client.post('/appointments/', data=appt_data, follow=False)
    assert res_appt.status_code == 302, f"Expected 302 redirect from appointment entry, got {res_appt.status_code}"

    appt = Appointment.objects.filter(patient=patient, doctor=doctor, appointment_date='2026-11-25').first()
    assert appt is not None, "Appointment was not created"
    assert appt.token_number, "Token number was not assigned"

    expected_consult_url = f"/consultations/new/?patient_id={patient.id}&appointment_id={appt.id}"
    assert res_appt['Location'] == expected_consult_url, f"Expected redirect to {expected_consult_url}, got {res_appt['Location']}"
    print(f" -> [PASS] Appointment registered with Token: {appt.token_number}")
    print(f" -> [PASS] Automatically redirected to Doctor Checkup: {res_appt['Location']}")

    # -------------------------------------------------------------
    # STAGE 3A: DOCTOR CHECKUP -> IF YOU WANT MEANS GO TO LAB
    # -------------------------------------------------------------
    print("\n[Stage 3A] Doctor Checkup WITH Lab Tests (Doctor wants lab)...")
    lab_test = LabTest.objects.filter(is_active=True).first()
    assert lab_test is not None, "Lab test must exist"

    consult_data_with_lab = {
        'patient': patient.id,
        'doctor': doctor.id,
        'appointment': appt.id,
        'temperature': '101.2',
        'pulse': '88',
        'blood_pressure': '130/85',
        'respiratory_rate': '18',
        'spo2': '97',
        'height_cm': '175',
        'weight_kg': '72',
        'chief_complaints': 'High fever for 3 days and acute headache',
        'examination_notes': 'Throat congested, febrile',
        'diagnosis': 'Viral Pyrexia with suspected hematology alteration',
        'treatment_plan': 'Adequate hydration, bed rest, paracetamol',
        'med_name[]': ['Paracetamol 650mg'],
        'med_dosage[]': ['1 tablet'],
        'med_route[]': ['Oral'],
        'med_frequency[]': ['1-0-1'],
        'med_duration[]': ['5'],
        'med_instructions[]': ['After meals'],
        'lab_tests[]': [lab_test.id],
        'target_destination': 'lab'
    }

    res_consult_lab = client.post('/consultations/new/', data=consult_data_with_lab, follow=False)
    assert res_consult_lab.status_code == 302, f"Expected 302 redirect from consultation, got {res_consult_lab.status_code}"

    lab_order = LabOrder.objects.filter(patient=patient, items__test=lab_test).first()
    assert lab_order is not None, "Lab Order was not created"
    expected_lab_url = f"/laboratory/{lab_order.pk}/"
    assert res_consult_lab['Location'] == expected_lab_url, f"Expected redirect to {expected_lab_url}, got {res_consult_lab['Location']}"
    print(f" -> [PASS] Doctor Checkup recorded!")
    print(f" -> [PASS] Lab Order #{lab_order.order_number} generated with test: {lab_test.name}")
    print(f" -> [PASS] Automatically redirected to Laboratory: {res_consult_lab['Location']}")

    # Verify lab page renders and provides link to Pharmacy
    res_lab_page = client.get(expected_lab_url)
    assert res_lab_page.status_code == 200
    assert "Proceed to Pharmacy" in res_lab_page.content.decode('utf-8')
    print(" -> [PASS] Laboratory worksheet has 'Proceed to Pharmacy' next step ready")

    # -------------------------------------------------------------
    # STAGE 3B: DOCTOR CHECKUP -> DON'T WANT MEANS GO TO PHARMACY
    # -------------------------------------------------------------
    print("\n[Stage 3B] Doctor Checkup WITHOUT Lab Tests (Doctor doesn't want lab)...")
    # Register second patient to test the direct-to-pharmacy branch
    phone_b = "+91 9888877772"
    Patient.objects.filter(phone=phone_b).delete()
    client.post('/patients/', data={
        'first_name': 'Meera',
        'last_name': 'Nair',
        'phone': phone_b,
        'gender': 'F',
    })
    patient_b = Patient.objects.get(phone=phone_b)

    # Reception checkin for patient_b
    appt_b = Appointment.objects.create(
        clinic=clinic,
        doctor=doctor,
        patient=patient_b,
        appointment_date='2026-11-25',
        appointment_time='11:30',
        status='IN_CONSULTATION'
    )

    consult_data_no_lab = {
        'patient': patient_b.id,
        'doctor': doctor.id,
        'appointment': appt_b.id,
        'temperature': '98.6',
        'pulse': '72',
        'blood_pressure': '120/80',
        'chief_complaints': 'Seasonal allergic rhinitis and sneezing',
        'diagnosis': 'Mild Allergic Rhinitis',
        'treatment_plan': 'Avoid dust, take antihistamine',
        'med_name[]': ['Cetirizine 10mg'],
        'med_dosage[]': ['1 tablet'],
        'med_route[]': ['Oral'],
        'med_frequency[]': ['0-0-1'],
        'med_duration[]': ['3'],
        'med_instructions[]': ['At bedtime'],
        # NO lab_tests[]!
        'target_destination': 'pharmacy'
    }

    res_consult_pharmacy = client.post('/consultations/new/', data=consult_data_no_lab, follow=False)
    assert res_consult_pharmacy.status_code == 302, f"Expected 302, got {res_consult_pharmacy.status_code}"

    consultation_b = Consultation.objects.filter(patient=patient_b).first()
    assert consultation_b is not None
    expected_pharmacy_url = f"/pharmacy/dispense/new/?patient_id={patient_b.pk}&consultation_id={consultation_b.pk}"
    assert res_consult_pharmacy['Location'] == expected_pharmacy_url, f"Expected redirect to {expected_pharmacy_url}, got {res_consult_pharmacy['Location']}"
    print(f" -> [PASS] Doctor Checkup recorded (No Lab Ordered)!")
    print(f" -> [PASS] Automatically redirected directly to Pharmacy: {res_consult_pharmacy['Location']}")

    # -------------------------------------------------------------
    # STAGE 4: PHARMACY DISPENSING
    # -------------------------------------------------------------
    print("\n[Stage 4] Pharmacy Medication Dispensing...")
    res_pharm_page = client.get(expected_pharmacy_url)
    assert res_pharm_page.status_code == 200
    html_pharm = res_pharm_page.content.decode('utf-8')
    assert "Doctor Checkup Prescriptions" in html_pharm
    assert "Cetirizine 10mg" in html_pharm
    print(" -> [PASS] Pharmacy POS displays doctor's prescribed medications for dispensing")

    batch = MedicineBatch.objects.filter(quantity_in_stock__gt=0).first()
    assert batch is not None, "Batch needed to test dispensing"
    dispense_data = {
        'patient': patient_b.id,
        'consultation': consultation_b.id,
        'batch[]': [batch.id],
        'quantity[]': [2],
        'price[]': [str(batch.selling_price)],
        'notes': 'Dispensed as per Dr. consultation'
    }
    res_dispense = client.post('/pharmacy/dispense/new/', data=dispense_data, follow=False)
    assert res_dispense.status_code == 302, f"Expected 302 from dispense, got {res_dispense.status_code}"

    dispense_rec = DispenseRecord.objects.filter(patient=patient_b).first()
    assert dispense_rec is not None, "Dispense record was not created"
    assert dispense_rec.consultation == consultation_b, "Dispense record must link to consultation"
    print(f" -> [PASS] Dispensation #{dispense_rec.dispense_number} completed and linked to consultation!")

    print("\n=====================================================================")
    print("ALL 4 STAGES TESTED AND VERIFIED WORKING 100%!")
    print("1. Patient Registration -> 2. Reception Enter & Token -> 3. Doctor Checkup -> 4. Lab (If Wanted) OR Pharmacy (If Not)")
    print("=====================================================================")

if __name__ == '__main__':
    test_full_patient_flow()
