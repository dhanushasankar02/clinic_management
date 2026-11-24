from rest_framework import serializers
from apps.doctors.models import Doctor, Specialty, DoctorSchedule

class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = ['id', 'name', 'slug', 'description', 'icon']

class DoctorScheduleSerializer(serializers.ModelSerializer):
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)

    class Meta:
        model = DoctorSchedule
        fields = ['id', 'day_of_week', 'day_name', 'start_time', 'end_time', 'slot_duration']

class DoctorSerializer(serializers.ModelSerializer):
    specialty_name = serializers.CharField(source='specialty.name', read_only=True)
    schedules = DoctorScheduleSerializer(many=True, read_only=True)

    class Meta:
        model = Doctor
        fields = [
            'id', 'name', 'specialty', 'specialty_name', 'qualification',
            'experience_years', 'consultation_fee', 'phone', 'email',
            'bio', 'is_available', 'schedules'
        ]
