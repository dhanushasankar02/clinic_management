from django.urls import path
from apps.laboratory import views

app_name = 'laboratory'

urlpatterns = [
    path('', views.order_list, name='order_list'),
    path('new/', views.order_create, name='order_create'),
    path('<int:pk>/', views.order_detail, name='detail'),
    path('<int:pk>/print/', views.order_print_report, name='print_report'),
    path('catalogue/', views.test_catalogue, name='catalogue'),
]
