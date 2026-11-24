from django.urls import path
from apps.billing import views

app_name = 'billing'

urlpatterns = [
    path('', views.invoice_list, name='invoice_list'),
    path('invoices/', views.invoice_list, name='invoices_alias'),
    path('new/', views.invoice_create, name='invoice_create'),
    path('<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail_alias'),
    path('<int:pk>/print/', views.invoice_print, name='invoice_print'),
    path('invoices/<int:pk>/print/', views.invoice_print, name='invoice_print_alias'),
    path('services/', views.service_catalogue, name='services'),
    path('services/catalog/', views.service_catalogue, name='service_catalogue'),
]
