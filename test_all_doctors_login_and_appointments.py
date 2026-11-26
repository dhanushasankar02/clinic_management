import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from apps.doctors.models import Doctor
from apps.patients.models import Patient
from apps.appointments.models import Appointment
from apps.clinics.models import Clinic
from datetime import date, time

def test_all_doctors():
    print("=====================================================================")
    print("TESTING: ALL DOCTORS LOGIN & APPOINTMENT VISIBILITY ISOLATION")
    print("=====================================================================")

    clinic = Clinic.objects.first()
    today = date.today()

    doc_sarah = Doctor.objects.get(name__icontains='Sarah')
    doc_arun = Doctor.objects.get(name__icontains='Arun')
    doc_priya = Doctor.objects.get(name__icontains='Priya')
    doc_vikram = Doctor.objects.get(name__icontains='Vikram')

    doctors_map = {
        'dr_sarah': doc_sarah,
        'doctor': doc_arun,
        'dr_priya': doc_priya,
        'dr_vikram': doc_vikram,
    }

    client = Client()

    # 1. Verify all 4 doctors can authenticate and log in
    print("\n--- 1. Testing Login for All 4 Doctors ---")
    for uname, doc in doctors_map.items():
        client.logout()
        resp = client.post('/accounts/login/', {
            'username': uname,
            'password': 'doctor123'
        }, follow=False)
        assert resp.status_code == 302, f"Doctor {uname} login failed with {resp.status_code}"
        assert resp.url == '/dashboard/doctor/', f"Doctor {uname} redirected to {resp.url} instead of /dashboard/doctor/"
        print(f" -> [PASS] {doc.name} (username: {uname}) logged in successfully -> {resp.url}")

    # 2. Verify 1-Click fast demo logins for all doctors
    print("\n--- 2. Testing 1-Click Fast Sign-In for All Doctors ---")
    for uname, doc in doctors_map.items():
        client.logout()
        resp = client.get(f'/accounts/login/?demo={uname}', follow=False)
        assert resp.status_code == 302
        assert resp.url == '/dashboard/doctor/'
        print(f" -> [PASS] 1-Click Fast Login for {doc.name} (?demo={uname}) works perfectly!")

    # 3. Create distinct appointments for each doctor
    print("\n--- 3. Booking Distinct Appointments for Each Doctor ---")
    patient, _ = Patient.objects.get_or_create(
        clinic=clinic,
        phone="9988776655",
        defaults={'first_name': 'UniqueTestPatient', 'last_name': 'Exclusive'}
    )

    Appointment.objects.filter(patient=patient).delete()

    appt_sarah = Appointment.objects.create(
        clinic=clinic,
        doctor=doc_sarah,
        patient=patient,
        appointment_date=today,
        appointment_time=time(10, 0),
        status='BOOKED',
        reason='Dermatology consultation with Dr. Sarah'
    )

    appt_priya = Appointment.objects.create(
        clinic=clinic,
        doctor=doc_priya,
        patient=patient,
        appointment_date=today,
        appointment_time=time(11, 0),
        status='BOOKED',
        reason='Skin checkup with Dr. Priya'
    )

    appt_vikram = Appointment.objects.create(
        clinic=clinic,
        doctor=doc_vikram,
        patient=patient,
        appointment_date=today,
        appointment_time=time(12, 0),
        status='CONFIRMED',
        reason='Pediatric checkup with Dr. Vikram'
    )

    # 4. Verify Doctor Dashboard shows only that doctor's appointment
    print("\n--- 4. Verifying Dashboard & Appointments Exclusivity ---")
    
    # Log in as Dr. Sarah
    client.logout()
    client.force_login(doc_sarah.user)
    resp = client.get('/dashboard/doctor/')
    assert resp.status_code == 200
    html = resp.content.decode()
    assert 'Dermatology consultation with Dr. Sarah' in html, "Dr. Sarah must see her appointment on dashboard"
    assert 'Skin checkup with Dr. Priya' not in html, "Dr. Sarah MUST NOT see Dr. Priya's appointment"
    assert 'Pediatric checkup with Dr. Vikram' not in html, "Dr. Sarah MUST NOT see Dr. Vikram's appointment"
    print(" -> [PASS] Dr. Sarah's dashboard displays ONLY Dr. Sarah's appointments.")

    # Check appointments page for Dr. Sarah
    resp_appts = client.get('/appointments/')
    assert resp_appts.status_code == 200
    html_appts = resp_appts.content.decode()
    assert 'Dermatology consultation with Dr. Sarah' in html_appts
    assert 'Skin checkup with Dr. Priya' not in html_appts
    assert 'Pediatric checkup with Dr. Vikram' not in html_appts
    print(" -> [PASS] /appointments/ automatically filtered to Dr. Sarah!")

    # Log in as Dr. Priya
    client.logout()
    client.force_login(doc_priya.user)
    resp = client.get('/dashboard/doctor/')
    assert resp.status_code == 200
    html_priya = resp.content.decode()
    assert 'Skin checkup with Dr. Priya' in html_priya, "Dr. Priya must see her appointment on dashboard"
    assert 'Dermatology consultation with Dr. Sarah' not in html_priya, "Dr. Priya MUST NOT see Dr. Sarah's appointment"
    assert 'Pediatric checkup with Dr. Vikram' not in html_priya, "Dr. Priya MUST NOT see Dr. Vikram's appointment"
    print(" -> [PASS] Dr. Priya's dashboard displays ONLY Dr. Priya's appointments.")

    # Check appointments page for Dr. Priya
    resp_appts_priya = client.get('/appointments/')
    assert resp_appts_priya.status_code == 200
    html_appts_priya = resp_appts_priya.content.decode()
    assert 'Skin checkup with Dr. Priya' in html_appts_priya
    assert 'Dermatology consultation with Dr. Sarah' not in html_appts_priya
    assert 'Pediatric checkup with Dr. Vikram' not in html_appts_priya
    print(" -> [PASS] /appointments/ automatically filtered to Dr. Priya!")

    # Log in as Dr. Vikram
    client.logout()
    client.force_login(doc_vikram.user)
    resp = client.get('/dashboard/doctor/')
    assert resp.status_code == 200
    html_vikram = resp.content.decode()
    assert 'Pediatric checkup with Dr. Vikram' in html_vikram, "Dr. Vikram must see his appointment on dashboard"
    assert 'Dermatology consultation with Dr. Sarah' not in html_vikram, "Dr. Vikram MUST NOT see Dr. Sarah's appointment"
    assert 'Skin checkup with Dr. Priya' not in html_vikram, "Dr. Vikram MUST NOT see Dr. Priya's appointment"
    print(" -> [PASS] Dr. Vikram's dashboard displays ONLY Dr. Vikram's appointments.")

    # Check appointments page for Dr. Vikram
    resp_appts_vikram = client.get('/appointments/')
    assert resp_appts_vikram.status_code == 200
    html_appts_vikram = resp_appts_vikram.content.decode()
    assert 'Pediatric checkup with Dr. Vikram' in html_appts_vikram
    assert 'Dermatology consultation with Dr. Sarah' not in html_appts_vikram
    assert 'Skin checkup with Dr. Priya' not in html_appts_vikram
    print(" -> [PASS] /appointments/ automatically filtered to Dr. Vikram!")

    # Clean up test appointments
    appt_sarah.delete()
    appt_priya.delete()
    appt_vikram.delete()
    patient.delete()

    print("\n=====================================================================")
    print("ALL TESTS PASSED! ALL DOCTORS CAN LOG IN AND SEE ONLY THEIR APPOINTMENTS!")
    print("=====================================================================")

if __name__ == '__main__':
    test_all_doctors()
