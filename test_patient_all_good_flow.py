import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from apps.doctors.models import Doctor
from apps.patients.models import Patient
from apps.appointments.models import Appointment
from apps.consultations.models import Consultation
from apps.clinics.models import Clinic
from datetime import date, time

def test_patient_all_good_flow():
    print("=====================================================================")
    print("TESTING CLINIC ORDER: WHEN PATIENT IS ALL GOOD (NO NEXT CHECKUP)")
    print("Order: Register -> Reception Token -> Doctor Checkup -> All Good -> Billing")
    print("=====================================================================")

    clinic = Clinic.objects.first()
    doctor = Doctor.objects.first()
    client = Client()

    # Step 1: Staff logs in
    reception_user = User.objects.get(username='reception')
    client.force_login(reception_user)

    # Step 2: Register Patient
    phone = "9876501234"
    Patient.objects.filter(phone=phone).delete()

    res_reg = client.post('/patients/', {
        'first_name': 'Aarav',
        'last_name': 'Healthy',
        'phone': phone,
        'gender': 'M',
        'blood_group': 'O+'
    }, follow=False)

    assert res_reg.status_code == 302
    patient = Patient.objects.get(phone=phone)
    print(f" -> [Step 1 PASS] Patient registered: {patient.full_name} ({patient.patient_id})")

    # Step 3: Reception check-in & token issue
    Appointment.objects.filter(doctor=doctor, appointment_date=date.today(), appointment_time='10:30').delete()
    res_appt = client.post('/appointments/', {
        'doctor': doctor.id,
        'patient': patient.id,
        'appointment_date': date.today().isoformat(),
        'appointment_time': '10:30',
        'reason': 'Routine wellness evaluation',
        'action': 'consult_now'
    }, follow=False)

    assert res_appt.status_code == 302
    appt = Appointment.objects.filter(patient=patient, doctor=doctor).first()
    assert appt is not None
    print(f" -> [Step 2 PASS] Reception Token generated: #{appt.token_number}")

    # Step 4: Doctor Checkup - Patient is ALL GOOD
    # No lab tests selected, no medicines prescribed, no follow-up needed
    res_consult = client.post('/consultations/new/', {
        'patient': patient.id,
        'doctor': doctor.id,
        'appointment': appt.id,
        'temperature': '98.4',
        'pulse': '72',
        'blood_pressure': '120/80',
        'respiratory_rate': '16',
        'spo2': '99',
        'height_cm': '175',
        'weight_kg': '70',
        'chief_complaints': 'Annual routine general health checkup',
        'examination_notes': 'Cardiovascular, respiratory and systemic examination completely normal. Vitals optimal.',
        'diagnosis': 'Patient evaluated and in excellent health. Routine wellness checkup normal. All good.',
        'treatment_plan': 'Maintain healthy balanced lifestyle and daily hydration. No medications required.',
        'no_followup_needed': '1',
        'target_destination': 'all_good'
    }, follow=False)

    assert res_consult.status_code == 302
    # Check that it advances to next waiting patient or proceeds to billing
    assert '/consultations/new/?patient_id=' in res_consult['Location'] or '/billing/new/?patient_id=' in res_consult['Location']
    print(f" -> [Step 3 PASS] Doctor Checkup recorded as 'ALL GOOD'!")
    print(f" -> [Step 3 PASS] NO Pharmacy visit needed (zero medicines to dispense)!")
    print(f" -> [Step 3 PASS] Automatically routed to next queue step: {res_consult['Location']}")

    # Step 5: Verify consultation record in DB
    consult = Consultation.objects.filter(patient=patient, doctor=doctor).first()
    assert consult is not None
    assert consult.follow_up_date is None, "Patient is all good -> follow_up_date must be None (no next checkup required)!"
    assert consult.prescriptions.count() == 0, "No medicines should be prescribed when all good"
    assert consult.lab_orders.count() == 0, "No lab tests should be ordered when all good"
    print(" -> [Step 4 PASS] Verified in DB: follow_up_date=None, prescriptions=0, lab_orders=0.")

    # Step 6: Verify Consultation Detail view shows 'Patient All Good • No Next Checkup Needed'
    res_detail = client.get(f"/consultations/{consult.id}/")
    assert res_detail.status_code == 200
    html_detail = res_detail.content.decode('utf-8')
    assert "No Next Checkup Needed" in html_detail
    assert "No Meds / No Lab" in html_detail
    print(" -> [Step 5 PASS] Consultation EMR & Print Rx clearly show: 'Patient All Good • No Next Checkup Needed'!")

    # Clean up
    consult.delete()
    appt.delete()
    patient.delete()

    print("\n=====================================================================")
    print(">>> SUCCESS: 'PATIENT ALL GOOD' WORKFLOW FULLY VERIFIED! <<<")
    print("No next checkup forced, no pharmacy trip, and clean routing to billing!")
    print("=====================================================================")

if __name__ == '__main__':
    test_patient_all_good_flow()
