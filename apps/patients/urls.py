from django.urls import path
from apps.patients.views import patient_list, patient_detail

app_name = 'patients'

urlpatterns = [
    path('', patient_list, name='list'),
    path('<int:pk>/', patient_detail, name='detail'),
]
