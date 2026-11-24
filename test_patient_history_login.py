import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from apps.patients.models import Patient
from apps.clinics.models import Clinic
from apps.accounts.models import UserProfile
from apps.consultations.models import Consultation
from apps.doctors.models import Doctor

def test_patient_history_and_registration():
    print("=====================================================================")
    print("TESTING: ALREADY REGISTERED PATIENT vs FIRST TIME NEW PATIENT")
    print("=====================================================================")
    
    client = Client()
    clinic = Clinic.objects.first()
    doctor = Doctor.objects.first()
    
    # 1. Staff login (receptionist)
    reception_user = User.objects.get(username='reception')
    client.force_login(reception_user)
    
    # Scenario A: Register brand new patient for the first time
    phone_new = "9998881234"
    Patient.objects.filter(phone=phone_new).delete()
    
    resp_new = client.post('/patients/', {
        'first_name': 'NewFirstTime',
        'last_name': 'Patient',
        'phone': phone_new,
        'gender': 'M',
        'blood_group': 'O+'
    }, follow=False)
    
    assert resp_new.status_code == 302, f"Expected 302, got {resp_new.status_code}"
    assert "new_patient=1" in resp_new.url, f"Expected new_patient=1 for first time patient, got {resp_new.url}"
    print(f" -> [PASS] New First-Time Patient redirected to Reception Check-in: {resp_new.url}")
    
    # Scenario B: Enter an ALREADY REGISTERED patient
    resp_existing = client.post('/patients/', {
        'first_name': 'NewFirstTime',
        'last_name': 'Patient',
        'phone': phone_new,
        'gender': 'M',
        'blood_group': 'O+'
    }, follow=False)
    
    pat_obj = Patient.objects.get(phone=phone_new)
    assert resp_existing.status_code == 302, f"Expected 302, got {resp_existing.status_code}"
    assert resp_existing.url == f"/patients/{pat_obj.id}/", f"Expected /patients/{pat_obj.id}/, got {resp_existing.url}"
    assert "new_patient=1" not in resp_existing.url, f"Already registered patient must not have new_patient=1!"
    print(f" -> [PASS] Already Registered Patient redirected directly to Medical History: {resp_existing.url}")
    
    # Scenario C: Brand new patient logs into portal for the first time
    user_brand_new = User.objects.create_user(username='first_timer_patient', password='password123')
    UserProfile.objects.create(user=user_brand_new, clinic=clinic, role='PATIENT')
    client.logout()
    
    login_resp = client.post('/accounts/login/', {
        'username': 'first_timer_patient',
        'password': 'password123'
    }, follow=False)
    assert login_resp.status_code == 302
    assert login_resp.url == '/portal/', f"Expected /portal/, got {login_resp.url}"
    print(f" -> [PASS] First-Time New Patient login opens Dashboard: {login_resp.url}")
    
    # Scenario D: Already registered patient with medical history logs in
    pat_with_history = Patient.objects.filter(consultations__isnull=False).first()
    assert pat_with_history is not None, "Need at least one patient with consultation"
    patient_user = pat_with_history.ensure_user_account()
    patient_user.set_password('password123')
    patient_user.save()
    
    client.logout()
    login_resp_existing = client.post('/accounts/login/', {
        'username': patient_user.username,
        'password': 'password123'
    }, follow=False)
    
    assert login_resp_existing.status_code == 302
    assert login_resp_existing.url == '/portal/medical-records/', f"Expected /portal/medical-records/, got {login_resp_existing.url}"
    print(f" -> [PASS] Already Registered Patient with History login opens Medical History: {login_resp_existing.url}")
    
    # Clean up test user
    user_brand_new.delete()
    print("=====================================================================")
    print("ALL TESTS PASSED! Only new patients do first-time flow; existing patients open medical history.")
    print("=====================================================================")

if __name__ == '__main__':
    test_patient_history_and_registration()
