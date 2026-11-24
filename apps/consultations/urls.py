from django.urls import path
from apps.consultations import views

app_name = 'consultations'

urlpatterns = [
    path('', views.consultation_list, name='list'),
    path('new/', views.consultation_create, name='create'),
    path('start/<int:appointment_id>/', views.consultation_create, name='start'),
    path('<int:appointment_id>/start/', views.consultation_create, name='start_alt'),
    path('<int:pk>/', views.consultation_detail, name='detail'),
    path('<int:pk>/print/', views.consultation_print_rx, name='print_rx'),
]
