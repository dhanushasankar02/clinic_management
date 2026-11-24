import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from django.test import Client
from apps.doctors.models import Doctor
from apps.patients.models import Patient
from apps.appointments.models import Appointment, AppointmentNotification
from apps.clinics.models import Clinic

print("=====================================================================")
print("TESTING EXCLUSIVE DOCTOR APPOINTMENT NOTIFICATIONS")
print("Requirement: When patient is appointed to a doctor, notification goes")
print("ONLY to THAT doctor, and NOT to other doctors!")
print("=====================================================================")

clinic = Clinic.objects.first()

# 1. Fetch our doctors and their linked user accounts
doc_sarah = Doctor.objects.filter(name__icontains='Sarah').first()
doc_arun = Doctor.objects.filter(name__icontains='Arun').first()

assert doc_sarah is not None and doc_sarah.user is not None, "Dr. Sarah Jenkins must have a linked user"
assert doc_arun is not None and doc_arun.user is not None, "Dr. Arun Sharma must have a linked user"

print(f"Doctor A: Dr. {doc_sarah.name} -> User: {doc_sarah.user.username}")
print(f"Doctor B: Dr. {doc_arun.name} -> User: {doc_arun.user.username}")

# Clear previous test data for cleanliness
Patient.objects.filter(phone__in=['+91 9111122221', '+91 9333344443']).delete()
AppointmentNotification.objects.filter(user__in=[doc_sarah.user, doc_arun.user]).delete()

# 2. Book an appointment for Dr. Sarah via Reception
c_rec = Client()
c_rec.post('/accounts/login/', {'username': 'reception', 'password': 'reception123'})

res_book = c_rec.post('/appointments/', {
    'action': 'consult_now',
    'patient_name': 'Exclusive Sarah Patient',
    'patient_phone': '+91 9111122221',
    'doctor': doc_sarah.id,
    'appointment_date': '2026-11-23',
    'appointment_time': '12:30',
    'reason': 'Cardiac Consultation with Dr. Sarah'
})
assert res_book.status_code == 302, "Appointment booking failed"

# Check notifications in DB
sarah_notifs = AppointmentNotification.objects.filter(user=doc_sarah.user)
arun_notifs = AppointmentNotification.objects.filter(user=doc_arun.user)

assert sarah_notifs.count() == 1, f"Dr. Sarah Jenkins must have 1 notification, got {sarah_notifs.count()}"
assert arun_notifs.count() == 0, f"Dr. Arun Sharma must have 0 notifications for Dr. Sarah's appointment, got {arun_notifs.count()}"

sarah_notif = sarah_notifs.first()
print(f"[PASS 1] Notification created exclusively for Dr. Sarah: '{sarah_notif.message}'")
print(f"[PASS 1] Dr. Arun received ZERO notifications for Dr. Sarah's patient.")

# 3. Test Dr. Sarah's Dashboard View vs Dr. Arun's Dashboard View
c_sarah = Client()
c_sarah.post('/accounts/login/', {'username': doc_sarah.user.username, 'password': 'doctor123'})
res_sarah_dash = c_sarah.get('/dashboard/doctor/')
assert res_sarah_dash.status_code == 200

# Dr. Sarah should see her appointment in her dashboard
sarah_content = res_sarah_dash.content.decode('utf-8')
assert 'Exclusive Sarah Patient' in sarah_content, "Dr. Sarah must see her patient on her dashboard"
assert 'Cardiac Consultation with Dr. Sarah' in sarah_content or 'Consultation' in sarah_content

c_arun = Client()
c_arun.post('/accounts/login/', {'username': doc_arun.user.username, 'password': 'doctor123'})
res_arun_dash = c_arun.get('/dashboard/doctor/')
assert res_arun_dash.status_code == 200

# Dr. Arun MUST NOT see Dr. Sarah's appointment on his dashboard
arun_content = res_arun_dash.content.decode('utf-8')
assert 'Exclusive Sarah Patient' not in arun_content, "Dr. Arun MUST NOT see Dr. Sarah's patient on his dashboard!"
print("[PASS 2] Dr. Sarah's dashboard displays her patient. Dr. Arun's dashboard DOES NOT show her patient.")

# 4. Now Book an appointment for Dr. Arun via Portal
c_patient = Client()
# Using an existing patient account or guest portal
pat = Patient.objects.first()
res_book_arun = c_rec.post('/appointments/', {
    'action': 'book_and_queue',
    'patient_name': 'Exclusive Arun Patient',
    'patient_phone': '+91 9333344443',
    'doctor': doc_arun.id,
    'appointment_date': '2026-11-23',
    'appointment_time': '14:00',
    'reason': 'Checkup with Dr. Arun'
})
assert res_book_arun.status_code == 302

# Check notifications now
sarah_notifs_after = AppointmentNotification.objects.filter(user=doc_sarah.user)
arun_notifs_after = AppointmentNotification.objects.filter(user=doc_arun.user)

assert sarah_notifs_after.count() == 1, f"Dr. Sarah should still have only 1 notification, got {sarah_notifs_after.count()}"
assert arun_notifs_after.count() == 1, f"Dr. Arun should now have 1 notification, got {arun_notifs_after.count()}"

arun_notif = arun_notifs_after.first()
print(f"[PASS 3] Dr. Arun's appointment created notification exclusively for Dr. Arun: '{arun_notif.message}'")
print(f"[PASS 3] Dr. Sarah received ZERO notifications for Dr. Arun's patient.")

# 5. Check Staff Notifications Center endpoint
res_sarah_inbox = c_sarah.get('/communication/notifications/')
assert res_sarah_inbox.status_code == 200
sarah_inbox_content = res_sarah_inbox.content.decode('utf-8')
assert 'Exclusive Sarah Patient' in sarah_inbox_content
assert 'Exclusive Arun Patient' not in sarah_inbox_content, "Dr. Sarah's notification inbox must not show Dr. Arun's patient"

res_arun_inbox = c_arun.get('/communication/notifications/')
assert res_arun_inbox.status_code == 200
arun_inbox_content = res_arun_inbox.content.decode('utf-8')
assert 'Exclusive Arun Patient' in arun_inbox_content
assert 'Exclusive Sarah Patient' not in arun_inbox_content, "Dr. Arun's notification inbox must not show Dr. Sarah's patient"

print("[PASS 4] Notification Center verified: Each doctor sees ONLY their own appointment alerts!")

print("\n=====================================================================")
print(">>> ALL TESTS PASSED: APPOINTMENT NOTIFICATIONS ROUTE EXCLUSIVELY <<<")
print(">>> TO THAT SPECIFIC DOCTOR. NO OTHER DOCTORS RECEIVE THEM!       <<<")
print("=====================================================================")
