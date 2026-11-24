from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter

from apps.doctors.views import DoctorViewSet
from apps.patients.views import PatientViewSet
from apps.appointments.views import AppointmentViewSet
from apps.consultations.views import ConsultationViewSet, PrescriptionItemViewSet
from apps.laboratory.views import LabTestViewSet, LabOrderViewSet
from apps.pharmacy.views import MedicineViewSet, DispenseRecordViewSet
from apps.billing.views import ServiceViewSet, InvoiceViewSet, PaymentViewSet

# REST API Router
api_router = DefaultRouter()
api_router.register(r'doctors', DoctorViewSet, basename='api-doctors')
api_router.register(r'patients', PatientViewSet, basename='api-patients')
api_router.register(r'appointments', AppointmentViewSet, basename='api-appointments')
api_router.register(r'consultations', ConsultationViewSet, basename='api-consultations')
api_router.register(r'prescriptions', PrescriptionItemViewSet, basename='api-prescriptions')
api_router.register(r'lab-tests', LabTestViewSet, basename='api-lab-tests')
api_router.register(r'lab-orders', LabOrderViewSet, basename='api-lab-orders')
api_router.register(r'medicines', MedicineViewSet, basename='api-medicines')
api_router.register(r'dispensations', DispenseRecordViewSet, basename='api-dispensations')
api_router.register(r'services', ServiceViewSet, basename='api-services')
api_router.register(r'invoices', InvoiceViewSet, basename='api-invoices')
api_router.register(r'payments', PaymentViewSet, basename='api-payments')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('portal/', include('apps.portal.urls', namespace='portal')),
    path('', include('apps.dashboard.urls', namespace='dashboard')),
    path('clinics/', include('apps.clinics.urls', namespace='clinics')),
    path('doctors/', include('apps.doctors.urls', namespace='doctors')),
    path('patients/', include('apps.patients.urls', namespace='patients')),
    path('appointments/', include('apps.appointments.urls', namespace='appointments')),
    path('consultations/', include('apps.consultations.urls', namespace='consultations')),
    path('laboratory/', include('apps.laboratory.urls', namespace='laboratory')),
    path('pharmacy/', include('apps.pharmacy.urls', namespace='pharmacy')),
    path('billing/', include('apps.billing.urls', namespace='billing')),
    path('reports/', include('apps.reports.urls', namespace='reports')),
    path('communication/', include('apps.communication.urls', namespace='communication')),
    path('chatbot/', include('apps.chatbot.urls', namespace='chatbot')),
    path('api/', include(api_router.urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
