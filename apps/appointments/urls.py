from django.urls import path
from apps.appointments import views

app_name = 'appointments'

urlpatterns = [
    path('', views.appointment_list, name='list'),
    path('queue/', views.queue_board, name='queue_board'),
    path('availability/', views.doctor_availability_list, name='availability'),
    path('<int:pk>/checkin/', views.check_in_patient, name='checkin'),
    path('<int:pk>/confirm/', views.appointment_confirm, name='confirm'),
    path('<int:pk>/reject/', views.appointment_reject, name='reject'),
    path('<int:pk>/reschedule/', views.appointment_reschedule, name='reschedule'),
    path('<int:pk>/cancel/', views.appointment_cancel, name='cancel'),
    path('<int:pk>/status/', views.appointment_status_update, name='status_update'),
    path('<int:pk>/slip/', views.print_visit_slip, name='print_slip'),
    path('<int:pk>/print_slip/', views.print_visit_slip, name='print_visit_slip'),
]
