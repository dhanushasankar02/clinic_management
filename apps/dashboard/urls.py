from django.urls import path
from apps.dashboard import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_index, name='index'),
    path('dashboard/doctor/', views.doctor_dashboard, name='doctor'),
    path('dashboard/receptionist/', views.receptionist_dashboard, name='receptionist'),
    path('dashboard/nurse/', views.nurse_dashboard, name='nurse'),
    path('dashboard/lab/', views.lab_dashboard, name='lab'),
    path('dashboard/pharmacist/', views.pharmacist_dashboard, name='pharmacist'),
    path('dashboard/accountant/', views.accountant_dashboard, name='accountant'),
    path('dashboard/inventory/', views.inventory_dashboard, name='inventory'),
    path('dashboard/tasks/', views.my_assigned_tasks, name='tasks'),
]
