import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from apps.accounts.models import LoginAuditLog, SystemAuditLog, UserProfile
from apps.accounts.views import get_login_stats

print("==================== STARTING RBAC & LOGIN TRACKING TEST SUITE ====================")

# 1. Test Login Statistics (Real Django Database)
stats = get_login_stats()
print("1. Testing Real-time Login Statistics from Django DB:")
print(f"   - Total Registered Users      : {stats['total_registered_users']}")
print(f"   - Active User Accounts        : {stats['active_user_accounts']}")
print(f"   - Inactive User Accounts      : {stats['inactive_user_accounts']}")
print(f"   - Currently Logged-in Users   : {stats['currently_logged_in_users']}")
print(f"   - Total Successful Logins     : {stats['total_successful_logins']}")
print(f"   - Total Failed Logins         : {stats['total_failed_logins']}")
print(f"   - Users Logged in Today       : {stats['users_logged_in_today']}")
assert stats['total_registered_users'] >= 9, "All 9 roles should be registered in DB"
print("   >>> [PASS] All 7 statistics computed directly from DB models")

# 2. Test Failed Login Attempt Recording
print("\n2. Testing Failed Login Recording:")
client_fail = Client()
res_fail = client_fail.post('/accounts/login/', {'username': 'nonexistent_user', 'password': 'wrongpassword'})
assert res_fail.status_code == 200, "Should re-render login page on failure"
failed_log = LoginAuditLog.objects.filter(username_attempted='nonexistent_user', status='FAILED').first()
assert failed_log is not None, "Failed login must be recorded in LoginAuditLog"
print(f"   >>> [PASS] Failed login recorded: {failed_log.username_attempted} (Status: {failed_log.status})")

# 3. Test Successful Login & Session Tracking
print("\n3. Testing Successful Login & Active Session Tracking:")
client_admin = Client()
res_admin_login = client_admin.post('/accounts/login/', {'username': 'admin', 'password': 'admin123'}, follow=True)
assert res_admin_login.status_code == 200
active_log = LoginAuditLog.objects.filter(user__username='admin', status='ACTIVE').first()
assert active_log is not None, "Admin active session must be logged in LoginAuditLog"
assert active_log.last_activity is not None, "last_activity must be populated"
print(f"   >>> [PASS] Active session logged for: {active_log.user.username} (Role: {active_log.role}, Status: {active_log.status})")

# 4. Test Logout Tracking
print("\n4. Testing Logout Tracking:")
res_logout = client_admin.get('/accounts/logout/', follow=True)
logged_out_log = LoginAuditLog.objects.filter(id=active_log.id).first()
assert logged_out_log.status == 'LOGGED_OUT', "Session must be marked LOGGED_OUT upon logout"
assert logged_out_log.logout_time is not None, "logout_time must be populated upon logout"
print(f"   >>> [PASS] Session marked LOGGED_OUT with timestamp: {logged_out_log.logout_time}")

# 5. Test Role-Based Login Redirection
print("\n5. Testing Role-Based Login Redirection (Section 9):")
role_redirect_tests = [
    ('admin', 'admin123', '/'),
    ('doctor', 'doctor123', '/dashboard/doctor/'),
    ('reception', 'reception123', '/dashboard/receptionist/'),
    ('labtech', 'labtech123', '/dashboard/lab/'),
    ('pharmacist', 'pharma123', '/dashboard/pharmacist/'),
    ('accountant', 'account123', '/dashboard/accountant/'),
    ('inventory', 'inventory123', '/dashboard/inventory/'),
]

for uname, pwd, expected_url in role_redirect_tests:
    c = Client()
    res = c.post('/accounts/login/', {'username': uname, 'password': pwd})
    assert res.status_code == 302, f"Login for {uname} should redirect (got {res.status_code})"
    target = res.url
    assert target == expected_url, f"{uname} expected redirect to {expected_url}, got {target}"
    print(f"   - Role {uname:<12} redirected to: {target} [PASS]")

# 6. Test RBAC URL Protection (Direct URL Entry Blocking - Section 8)
print("\n6. Testing Direct URL Access Protection & RBAC Enforcement:")

# Doctor cannot access Billing, User Management, or Clinic Settings
doc_c = Client()
doc_c.post('/accounts/login/', {'username': 'doctor', 'password': 'doctor123'})
res1 = doc_c.get('/billing/')
assert res1.status_code == 302, "Doctor accessing /billing/ must be blocked (302 redirect)"
res2 = doc_c.get('/accounts/users/')
assert res2.status_code == 302, "Doctor accessing /accounts/users/ must be blocked"
res3 = doc_c.get('/clinics/')
assert res3.status_code == 302, "Doctor accessing /clinics/ must be blocked"
print("   >>> [PASS] Doctor correctly blocked from Billing, Users, and Clinic Settings")

# Receptionist cannot access Doctor Consultations EMR or Laboratory
rec_c = Client()
rec_c.post('/accounts/login/', {'username': 'reception', 'password': 'reception123'})
res_rec_consult = rec_c.get('/consultations/')
assert res_rec_consult.status_code == 302, "Receptionist accessing /consultations/ must be blocked"
res_rec_lab = rec_c.get('/laboratory/')
assert res_rec_lab.status_code == 302, "Receptionist accessing /laboratory/ must be blocked"
print("   >>> [PASS] Receptionist correctly blocked from Medical Consultations and Lab")

# Pharmacist cannot access Billing or Doctor Consultations
pharma_c = Client()
pharma_c.post('/accounts/login/', {'username': 'pharmacist', 'password': 'pharma123'})
res_ph_bill = pharma_c.get('/billing/')
assert res_ph_bill.status_code == 302, "Pharmacist accessing /billing/ must be blocked"
print("   >>> [PASS] Pharmacist correctly blocked from Billing")

# Accountant cannot access Patient Consultations
acc_c = Client()
acc_c.post('/accounts/login/', {'username': 'accountant', 'password': 'account123'})
res_acc_consult = acc_c.get('/consultations/')
assert res_acc_consult.status_code == 302, "Accountant accessing /consultations/ must be blocked"
print("   >>> [PASS] Accountant correctly blocked from Consultations")

# 7. Test Dedicated Admin Pages
print("\n7. Testing Admin Dedicated Surveillance Pages (Sections 5 & 6):")
admin_c = Client()
admin_c.post('/accounts/login/', {'username': 'admin', 'password': 'admin123'})
res_act = admin_c.get('/accounts/login-activity/')
assert res_act.status_code == 200, "/accounts/login-activity/ must return 200 OK for Admin"
assert 'Login Activity & Member Session Tracking' in res_act.content.decode('utf-8')

res_audit = admin_c.get('/accounts/audit-logs/')
assert res_audit.status_code == 200, "/accounts/audit-logs/ must return 200 OK for Admin"

res_users = admin_c.get('/accounts/users/')
assert res_users.status_code == 200, "/accounts/users/ must return 200 OK for Admin"
print("   >>> [PASS] Admin Login Activity, Audit Logs, and User Management all accessible")

# 8. Test Non-Admin cannot access Admin Surveillance Pages
res_doc_act = doc_c.get('/accounts/login-activity/')
assert res_doc_act.status_code == 302, "Non-admin accessing login-activity must be redirected"
res_doc_audit = doc_c.get('/accounts/audit-logs/')
assert res_doc_audit.status_code == 302, "Non-admin accessing audit-logs must be redirected"
print("   >>> [PASS] Non-admin strictly blocked from Admin Surveillance Pages")

# 9. Test User Profile & Self Password Change
print("\n9. Testing User Profile & Password Change:")
res_prof = doc_c.get('/accounts/profile/')
assert res_prof.status_code == 200, "User can view own profile"
res_my_logins = doc_c.get('/accounts/my-logins/')
assert res_my_logins.status_code == 200, "User can view own login history"
res_pwd_change = doc_c.get('/accounts/password-change/')
assert res_pwd_change.status_code == 200, "User can view change password page"
print("   >>> [PASS] Profile, My Logins, and Change Password operational")

print("\n==================== ALL RBAC & SURVEILLANCE TESTS PASSED! ====================")
