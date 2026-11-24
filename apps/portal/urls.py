from django.urls import path
from apps.portal import views

app_name = 'portal'

urlpatterns = [
    path('', views.portal_dashboard, name='dashboard'),
    path('register/', views.portal_register, name='register'),
    path('login/', views.portal_login, name='login'),
    path('logout/', views.portal_logout, name='logout'),
    path('profile/', views.portal_profile, name='profile'),
    path('book/', views.portal_book_appointment, name='book_appointment'),
    path('appointments/', views.portal_appointments, name='my_appointments'),
    path('appointments/history/', views.portal_appointment_history, name='appointment_history'),
    path('appointments/<int:pk>/cancel/', views.portal_cancel_appointment, name='cancel_appointment'),
    path('prescriptions/', views.portal_prescriptions, name='my_prescriptions'),
    path('prescriptions/<int:pk>/', views.portal_prescription_detail, name='prescription_detail'),
    path('laboratory/', views.portal_lab_reports, name='my_lab_reports'),
    path('laboratory/<int:pk>/', views.portal_lab_report_detail, name='lab_report_detail'),
    path('medical-records/', views.portal_medical_records, name='my_medical_records'),
    path('notifications/', views.portal_notifications, name='notifications'),
    path('notifications/<int:pk>/read/', views.portal_notification_read, name='notification_read'),
    path('change-password/', views.portal_change_password, name='change_password'),
    path('api/slots/', views.api_available_slots, name='api_slots'),
]
