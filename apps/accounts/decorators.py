from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse

def get_dashboard_url_for_user(user):
    if not user.is_authenticated:
        return reverse('accounts:login')
    profile = getattr(user, 'profile', None)
    role = profile.role if profile else ('SUPER_ADMIN' if user.is_superuser else 'GUEST')
    
    if user.is_superuser or role in ['SUPER_ADMIN', 'CLINIC_ADMIN']:
        return reverse('dashboard:index')
    elif role == 'DOCTOR':
        return reverse('dashboard:doctor')
    elif role == 'RECEPTIONIST':
        return reverse('dashboard:receptionist')
    elif role == 'NURSE':
        return reverse('dashboard:nurse')
    elif role == 'LAB_TECH':
        return reverse('dashboard:lab')
    elif role == 'PHARMACIST':
        return reverse('dashboard:pharmacist')
    elif role == 'ACCOUNTANT':
        return reverse('dashboard:accountant')
    elif role == 'INVENTORY_MGR':
        return reverse('dashboard:inventory')
    elif role == 'PATIENT':
        # If already registered patient with prior history, open their medical history directly; new patients go to dashboard
        try:
            from apps.patients.models import Patient
            patient = getattr(user, 'patient_record', None) or Patient.objects.filter(user=user).first()
            if patient:
                has_history = (
                    patient.consultations.exists() or
                    patient.appointments.filter(status='COMPLETED').exists() or
                    patient.lab_orders.exists() or
                    patient.invoices.exists()
                )
                if has_history:
                    return reverse('portal:my_medical_records')
        except Exception:
            pass
        return reverse('portal:dashboard')
    return reverse('dashboard:index')


def role_required(allowed_roles):
    """
    Decorator to restrict view access to specific roles.
    Superusers always have access.
    Unauthorized users are redirected with an explicit access denied message.
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.warning(request, "Please sign in to access this clinic module.")
                return redirect(f"{reverse('accounts:login')}?next={request.get_full_path()}")

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            profile = getattr(request.user, 'profile', None)
            user_role = profile.role if profile else None

            if user_role in allowed_roles:
                return view_func(request, *args, **kwargs)

            # Not authorized
            role_display = profile.get_role_display() if profile else 'Staff'
            messages.error(request, f"Access Denied: Your account role ({role_display}) is not permitted to access this module.")
            referer = request.META.get('HTTP_REFERER')
            if referer and request.get_host() in referer and referer != request.build_absolute_uri():
                return redirect(referer)
            return redirect(get_dashboard_url_for_user(request.user))

        return _wrapped_view
    return decorator


def admin_required(view_func):
    """Shortcut decorator for Super Admin and Clinic Admin access only."""
    return role_required(['SUPER_ADMIN', 'CLINIC_ADMIN'])(view_func)
