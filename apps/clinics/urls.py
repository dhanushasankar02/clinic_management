from django.urls import path
from apps.clinics.views import clinic_detail

app_name = 'clinics'

urlpatterns = [
    path('', clinic_detail, name='detail'),
]
