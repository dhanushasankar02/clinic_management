from apps.accounts.models import UserProfile

def user_role_context(request):
    """Provides user role and permission flags to all templates."""
    if not request.user.is_authenticated:
        return {
            'current_user_role': 'ANONYMOUS',
            'current_user_role_display': 'Guest / Visitor',
            'is_admin': False,
            'is_doctor': False,
            'is_receptionist': False,
            'is_nurse': False,
            'is_lab_tech': False,
            'is_pharmacist': False,
            'is_accountant': False,
            'is_inventory_mgr': False,
            'is_patient': False,
            'can_view_patients': False,
            'can_view_appointments': False,
            'can_view_queue': False,
            'can_view_consultations': False,
            'can_view_laboratory': False,
            'can_view_pharmacy': False,
            'can_view_billing': False,
            'can_view_inventory': False,
            'can_view_reports': False,
            'can_view_admin_control': False,
            'can_manage_users': False,
        }

    is_super = request.user.is_superuser
    profile = getattr(request.user, 'profile', None)
    role = profile.role if profile else ('SUPER_ADMIN' if is_super else 'PATIENT')
    is_admin = is_super or role in ['SUPER_ADMIN', 'CLINIC_ADMIN']
    is_doctor = role == 'DOCTOR'
    is_receptionist = role == 'RECEPTIONIST'
    is_nurse = role == 'NURSE'
    is_lab_tech = role == 'LAB_TECH'
    is_pharmacist = role == 'PHARMACIST'
    is_accountant = role == 'ACCOUNTANT'
    is_inventory_mgr = role == 'INVENTORY_MGR'
    is_patient = role == 'PATIENT'

    unread_notifications_count = 0
    try:
        from apps.appointments.models import AppointmentNotification
        unread_notifications_count = AppointmentNotification.objects.filter(user=request.user, is_read=False).count()
    except Exception:
        pass

    return {
        'user_profile': profile,
        'unread_notifications_count': unread_notifications_count,
        'current_user_role': role,
        'current_user_role_display': profile.get_role_display() if profile else ('Super Admin' if is_super else 'Staff User'),
        'is_admin': is_admin,
        'is_doctor': is_doctor,
        'is_receptionist': is_receptionist,
        'is_nurse': is_nurse,
        'is_lab_tech': is_lab_tech,
        'is_pharmacist': is_pharmacist,
        'is_accountant': is_accountant,
        'is_inventory_mgr': is_inventory_mgr,
        'is_patient': is_patient,
        # Fine-grained granular permissions for seamless clinical workflow
        'can_view_patients': is_admin or is_doctor or is_receptionist or is_nurse or is_pharmacist or is_lab_tech or is_accountant,
        'can_view_appointments': is_admin or is_doctor or is_receptionist or is_nurse,
        'can_view_queue': is_admin or is_receptionist or is_doctor or is_nurse,
        'can_view_consultations': is_admin or is_doctor or is_nurse or is_receptionist or is_pharmacist,
        'can_view_laboratory': is_admin or is_lab_tech or is_doctor or is_nurse or is_receptionist,
        'can_view_pharmacy': is_admin or is_pharmacist or is_inventory_mgr or is_doctor or is_receptionist,
        'can_view_billing': is_admin or is_accountant or is_receptionist or is_doctor or is_pharmacist,
        'can_view_inventory': is_admin or is_inventory_mgr or is_pharmacist,
        'can_view_reports': is_admin or is_accountant or is_doctor,
        'can_view_admin_control': is_admin,
        'can_manage_users': is_admin,
    }
