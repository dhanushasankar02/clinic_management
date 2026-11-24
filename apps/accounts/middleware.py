from django.utils import timezone
from apps.accounts.models import LoginAuditLog

class ActivityTrackingMiddleware:
    """
    Tracks real-time user activity across requests and updates the last_activity
    timestamp on the active session audit log.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.session.session_key:
            try:
                LoginAuditLog.objects.filter(
                    user=request.user,
                    session_key=request.session.session_key,
                    status='ACTIVE'
                ).update(last_activity=timezone.now())
            except Exception:
                pass

        response = self.get_response(request)
        return response
