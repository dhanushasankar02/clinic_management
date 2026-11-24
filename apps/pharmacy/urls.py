from django.urls import path
from apps.pharmacy import views

app_name = 'pharmacy'

urlpatterns = [
    path('', views.pharmacy_dashboard, name='dashboard'),
    path('medicines/', views.medicine_list, name='medicine_list'),
    path('batches/add/', views.batch_add, name='batch_add'),
    path('batches/add/<int:medicine_id>/', views.batch_add, name='batch_add'),
    path('dispense/', views.dispense_list, name='dispense_list'),
    path('dispense/new/', views.dispense_create, name='dispense_create'),
    path('dispense/<int:pk>/', views.dispense_detail, name='dispense_detail'),
]
