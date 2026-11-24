from django.urls import path
from apps.doctors.views import doctor_list

app_name = 'doctors'

urlpatterns = [
    path('', doctor_list, name='list'),
]
