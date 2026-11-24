import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
import django
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta, date, time
from apps.clinics.models import Clinic
from apps.accounts.models import UserProfile
from apps.patients.models import Patient
from apps.doctors.models import Doctor, DoctorAvailability
from apps.appointments.models import Appointment, AppointmentNotification

def run_tests():
    print("=" * 60)
    print("RUNNING COMPREHENSIVE PATIENT PORTAL & RBAC TEST SUITE")
    print("=" * 60)
    client = Client()
    clinic = Clinic.objects.first()

    # 1. TEST PATIENT REGISTRATION
    print("\n[1] Testing Patient Self-Registration...")
    reg_username = "new_patient_test"
    User.objects.filter(username=reg_username).delete()
    Patient.objects.filter(phone='+1 (555) 432-1098').delete()

    reg_data = {
        'first_name': 'Aarav',
        'last_name': 'Kapoor',
        'email': 'aarav.kapoor@example.com',
        'phone': '+1 (555) 432-1098',
        'gender': 'MALE',
        'date_of_birth': '1992-05-14',
        'blood_group': 'B+',
        'allergies': 'Aspirin',
        'chronic_conditions': 'None',
        'address': '742 Evergreen Terrace, Springfield',
        'username': reg_username,
        'password': 'password123',
        'confirm_password': 'password123',
    }

    res = client.post('/portal/register/', reg_data, follow=True)
    assert res.status_code == 200, f"Registration failed with code {res.status_code}"
    user = User.objects.filter(username=reg_username).first()
    assert user is not None, "User was not created in DB"
    assert user.profile.role == 'PATIENT', f"User profile role is {user.profile.role}, expected PATIENT"
    patient = Patient.objects.filter(user=user).first()
    assert patient is not None, "Patient record was not linked to User"
    assert patient.patient_id.startswith('PAT-'), f"Patient ID {patient.patient_id} invalid"
    assert patient.blood_group == 'B+', "Blood group not saved correctly"
    print(f" -> [PASS] Patient '{patient.full_name}' ({patient.patient_id}) registered & logged in.")

    # 2. TEST PATIENT DASHBOARD & PORTAL SCREENS (11 EXACT SECTIONS)
    print("\n[2] Testing Patient Portal Navigation & Screens...")
    endpoints = [
        ('/portal/', "1. Dashboard Overview"),
        ('/portal/profile/', "2. My Profile"),
        ('/portal/book/', "3. Book Appointment"),
        ('/portal/appointments/', "4. My Appointments"),
        ('/portal/appointments/history/', "5. Appointment History"),
        ('/portal/prescriptions/', "6. My Prescriptions"),
        ('/portal/laboratory/', "7. My Lab Reports"),
        ('/portal/medical-records/', "8. My Medical Records"),
        ('/portal/notifications/', "9. Notifications"),
        ('/portal/change-password/', "10. Change Password"),
    ]

    for url, label in endpoints:
        r = client.get(url)
        assert r.status_code == 200, f"Endpoint {url} failed with status {r.status_code}"
        print(f" -> [PASS] {label}: {url} rendered OK (200)")

    # 3. TEST DOCTOR AVAILABILITY & SLOTS API
    print("\n[3] Testing Doctor Availability & Slot Generation API...")
    doctor = Doctor.objects.first()
    assert doctor is not None, "No doctor found in database"
    
    # Ensure doctor has availability for tomorrow
    tomorrow = timezone.localdate() + timedelta(days=1)
    day_weekday = tomorrow.weekday()

    avail, _ = DoctorAvailability.objects.update_or_create(
        doctor=doctor,
        working_day=day_weekday,
        defaults={
            'start_time': time(9, 0),
            'end_time': time(17, 0),
            'slot_duration': 15,
            'break_start': time(13, 0),
            'break_end': time(14, 0),
            'is_available': True,
            'is_leave': False,
        }
    )

    slot_url = f"/portal/api/slots/?doctor_id={doctor.id}&date={tomorrow.strftime('%Y-%m-%d')}"
    slot_res = client.get(slot_url)
    assert slot_res.status_code == 200, f"Slots API failed with status {slot_res.status_code}"
    data = slot_res.json()
    assert data.get('available') is True, f"Doctor should be available: {data}"
    slots = data.get('slots', [])
    assert len(slots) > 0, "No time slots returned for doctor"
    assert "09:00" in slots, "09:00 slot expected"
    assert "13:00" not in slots, "13:00 break slot should be excluded"
    print(f" -> [PASS] Slots API returned {len(slots)} valid slots (Break 13:00-14:00 correctly excluded).")

    # 4. TEST ONLINE APPOINTMENT BOOKING BY PATIENT
    print("\n[4] Testing Online Appointment Booking...")
    chosen_slot = slots[0]
    booking_data = {
        'doctor': doctor.id,
        'appointment_date': tomorrow.strftime('%Y-%m-%d'),
        'appointment_time': chosen_slot,
        'appointment_type': 'NEW',
        'reason': 'Chronic migraine symptoms',
        'notes': 'Preferred morning consultation',
    }
    book_res = client.post('/portal/book/', booking_data, follow=True)
    assert book_res.status_code == 200, f"Booking failed with status {book_res.status_code}"

    appt = Appointment.objects.filter(
        patient=patient,
        doctor=doctor,
        appointment_date=tomorrow,
        appointment_time=chosen_slot
    ).first()
    assert appt is not None, "Appointment was not created in database"
    assert appt.status == 'PENDING', f"Appointment status is {appt.status}, expected PENDING"
    assert appt.source == 'ONLINE', f"Appointment source is {appt.source}, expected ONLINE"
    assert appt.appointment_id.startswith('APT-'), f"Appointment ID {appt.appointment_id} invalid"

    # Verify notification created
    notif = AppointmentNotification.objects.filter(user=user, appointment=appt).first()
    assert notif is not None, "AppointmentNotification was not created for patient"
    assert notif.notification_type == 'BOOKED', f"Notification type is {notif.notification_type}"
    print(f" -> [PASS] Online Appointment #{appt.appointment_id} booked successfully (Status: PENDING).")
    print(f" -> [PASS] In-app notification delivered: '{notif.message}'")

    # 5. TEST DOUBLE-BOOKING PREVENTION
    print("\n[5] Testing Double-Booking Prevention...")
    duplicate_res = client.post('/portal/book/', booking_data, follow=True)
    # The view should reject it and stay on book page or show message
    same_slot_appts = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=tomorrow,
        appointment_time=chosen_slot
    ).exclude(status__in=['CANCELLED', 'REJECTED']).count()
    assert same_slot_appts == 1, f"Expected 1 appointment for slot, found {same_slot_appts} (Double booking occurred!)"
    print(" -> [PASS] Double booking strictly blocked: Slot conflict rejected.")

    # 6. TEST ADMIN / RECEPTIONIST CONFIRMATION
    print("\n[6] Testing Staff Appointment Confirmation & Notification...")
    admin_client = Client()
    logged_in = admin_client.login(username='admin', password='admin123')
    assert logged_in is True, "Admin login failed"

    confirm_res = admin_client.get(f'/appointments/{appt.id}/confirm/', follow=True)
    assert confirm_res.status_code == 200, f"Admin confirm failed with code {confirm_res.status_code}"
    appt.refresh_from_db()
    assert appt.status == 'CONFIRMED', f"Expected CONFIRMED, got {appt.status}"

    confirm_notif = AppointmentNotification.objects.filter(
        user=user,
        appointment=appt,
        notification_type='CONFIRMED'
    ).first()
    assert confirm_notif is not None, "Confirmation notification was not sent to patient"
    print(f" -> [PASS] Appointment #{appt.appointment_id} confirmed by Admin.")
    print(f" -> [PASS] Confirmation alert delivered to patient: '{confirm_notif.message}'")

    # 7. TEST PATIENT CANCELLATION
    print("\n[7] Testing Patient-Side Appointment Cancellation...")
    cancel_res = client.post(f'/portal/appointments/{appt.id}/cancel/', follow=True)
    assert cancel_res.status_code == 200, f"Cancel failed with status {cancel_res.status_code}"
    appt.refresh_from_db()
    assert appt.status == 'CANCELLED', f"Expected CANCELLED, got {appt.status}"
    cancel_notif = AppointmentNotification.objects.filter(
        user=user,
        appointment=appt,
        notification_type='CANCELLED'
    ).first()
    assert cancel_notif is not None, "Cancellation notification was not sent"
    print(f" -> [PASS] Patient successfully cancelled appointment #{appt.appointment_id}.")

    # 8. TEST SECURITY & RBAC ENFORCEMENT
    print("\n[8] Testing Security Restrictions & Unauthorized URL Protection...")
    # Patient tries to access Admin Dashboard (/)
    admin_url_res = client.get('/')
    assert admin_url_res.status_code == 302, f"Direct access to / returned {admin_url_res.status_code}, expected 302 redirect"
    assert '/portal/' in admin_url_res.url
    print(f" -> [PASS] Patient blocked from Admin Dashboard (Redirected to: {admin_url_res.url})")

    # Patient tries to access Invoices (/billing/)
    inv_res = client.get('/billing/')
    assert inv_res.status_code == 302, f"Direct access to /billing/ returned {inv_res.status_code}, expected 302"
    print(" -> [PASS] Patient blocked from /billing/ (Redirected to authorized portal)")

    # Unauthenticated user tries to access /portal/
    anon_client = Client()
    anon_res = anon_client.get('/portal/')
    assert anon_res.status_code == 302, f"Anonymous access to /portal/ returned {anon_res.status_code}, expected 302"
    assert '/accounts/login/' in anon_res.url
    print(" -> [PASS] Anonymous user blocked from /portal/ (Redirected to login)")

    print("\n" + "=" * 60)
    print("ALL PATIENT PORTAL & RBAC TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == '__main__':
    run_tests()
