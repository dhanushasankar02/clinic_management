from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q, Avg
from rest_framework import viewsets
from apps.doctors.models import Doctor, Specialty, DoctorSchedule
from apps.doctors.serializers import DoctorSerializer, SpecialtySerializer
from apps.clinics.models import Clinic
from apps.accounts.decorators import role_required


@role_required(['SUPER_ADMIN', 'CLINIC_ADMIN', 'RECEPTIONIST', 'DOCTOR', 'NURSE'])
def doctor_list(request):
    clinic = Clinic.objects.first()
    doctors_qs = Doctor.objects.filter(clinic=clinic).select_related('specialty').prefetch_related('schedules')
    specialties = Specialty.objects.all()

    # Search & Filters
    search = request.GET.get('q', '').strip()
    specialty_filter = request.GET.get('specialty', '').strip()
    status_filter = request.GET.get('status', '').strip()
    view_mode = request.GET.get('view', 'grid').strip()

    if search:
        doctors_qs = doctors_qs.filter(
            Q(name__icontains=search) |
            Q(qualification__icontains=search) |
            Q(specialty__name__icontains=search) |
            Q(phone__icontains=search) |
            Q(email__icontains=search)
        )

    if specialty_filter:
        doctors_qs = doctors_qs.filter(specialty_id=specialty_filter)

    if status_filter == 'available':
        doctors_qs = doctors_qs.filter(is_available=True)
    elif status_filter == 'offline':
        doctors_qs = doctors_qs.filter(is_available=False)

    doctors = doctors_qs.all()

    # Metrics for Top Stat Bar
    all_clinic_doctors = Doctor.objects.filter(clinic=clinic)
    total_doctors = all_clinic_doctors.count()
    available_doctors = all_clinic_doctors.filter(is_available=True).count()
    specialties_count = specialties.count()
    avg_fee = all_clinic_doctors.aggregate(avg=Avg('consultation_fee'))['avg'] or 0

    # Role check for management operations
    is_super = request.user.is_superuser
    profile = getattr(request.user, 'profile', None)
    can_manage = is_super or (profile and profile.role in ['SUPER_ADMIN', 'CLINIC_ADMIN'])

    if request.method == 'POST':
        if not can_manage:
            messages.error(request, "Access restricted: Only Clinic Administrators can manage doctors.")
            return redirect('doctors:list')

        action = request.POST.get('action', 'add')

        # 1. EDIT DOCTOR
        if action == 'edit':
            doctor_id = request.POST.get('doctor_id')
            doc = get_object_or_404(Doctor, id=doctor_id, clinic=clinic)
            name = request.POST.get('name', '').strip()
            specialty_id = request.POST.get('specialty')
            qualification = request.POST.get('qualification', '').strip()
            experience = request.POST.get('experience_years')
            fee = request.POST.get('consultation_fee')
            phone = request.POST.get('phone', '').strip()
            email = request.POST.get('email', '').strip()
            bio = request.POST.get('bio', '').strip()
            is_avail = request.POST.get('is_available') == 'on'

            if name:
                doc.name = name
                doc.specialty = Specialty.objects.filter(id=specialty_id).first() if specialty_id else None
                if qualification:
                    doc.qualification = qualification
                if experience:
                    try: doc.experience_years = int(experience)
                    except ValueError: pass
                if fee:
                    try: doc.consultation_fee = float(fee)
                    except ValueError: pass
                doc.phone = phone
                doc.email = email
                doc.bio = bio
                doc.is_available = is_avail
                if 'photo' in request.FILES:
                    doc.photo = request.FILES['photo']
                photo_url_val = request.POST.get('photo_url', '').strip()
                if photo_url_val:
                    doc.photo_url = photo_url_val
                doc.save()
                messages.success(request, f"Dr. {doc.name}'s profile has been updated successfully.")
            return redirect('doctors:list')

        # 2. TOGGLE AVAILABILITY
        elif action == 'toggle_status':
            doctor_id = request.POST.get('doctor_id')
            doc = get_object_or_404(Doctor, id=doctor_id, clinic=clinic)
            doc.is_available = not doc.is_available
            doc.save(update_fields=['is_available'])
            status_text = "Available" if doc.is_available else "Offline"
            messages.info(request, f"Dr. {doc.name} status updated to {status_text}.")
            return redirect('doctors:list')

        # 3. DELETE DOCTOR
        elif action == 'delete':
            doctor_id = request.POST.get('doctor_id')
            doc = get_object_or_404(Doctor, id=doctor_id, clinic=clinic)
            doc_name = doc.name
            if hasattr(doc, 'appointments') and doc.appointments.exists():
                doc.is_available = False
                doc.save(update_fields=['is_available'])
                messages.warning(request, f"Dr. {doc_name} has existing clinical appointments on file. The doctor has been marked Offline.")
            else:
                doc.delete()
                messages.success(request, f"Dr. {doc_name} was removed successfully.")
            return redirect('doctors:list')

        # 4. MANAGE SCHEDULE / WORKING HOURS
        elif action == 'update_schedule':
            doctor_id = request.POST.get('doctor_id')
            doc = get_object_or_404(Doctor, id=doctor_id, clinic=clinic)
            start_str = request.POST.get('start_time', '09:00')
            end_str = request.POST.get('end_time', '14:00')
            days = request.POST.getlist('days')

            if days:
                DoctorSchedule.objects.filter(doctor=doc).delete()
                for d in days:
                    DoctorSchedule.objects.create(
                        doctor=doc,
                        day_of_week=int(d),
                        start_time=start_str,
                        end_time=end_str,
                        slot_duration=15
                    )
                messages.success(request, f"Duty hours updated for Dr. {doc.name} ({len(days)} working days).")
            else:
                messages.error(request, "Please select at least one working day.")
            return redirect('doctors:list')

        # 5. ADD NEW DOCTOR
        else:
            name = request.POST.get('name', '').strip()
            specialty_id = request.POST.get('specialty')
            qualification = request.POST.get('qualification', 'MBBS, MD').strip()
            experience = request.POST.get('experience_years', 5)
            fee = request.POST.get('consultation_fee', 500)
            phone = request.POST.get('phone', '').strip()
            email = request.POST.get('email', '').strip()
            bio = request.POST.get('bio', '').strip()
            is_avail = request.POST.get('is_available') == 'on' or True

            if name and clinic:
                specialty = Specialty.objects.filter(id=specialty_id).first() if specialty_id else None
                photo_file = request.FILES.get('photo')
                photo_url_val = request.POST.get('photo_url', '').strip()
                new_doc = Doctor.objects.create(
                    clinic=clinic,
                    name=name,
                    specialty=specialty,
                    qualification=qualification or 'MBBS',
                    experience_years=int(experience) if experience else 1,
                    consultation_fee=float(fee) if fee else 500.0,
                    phone=phone,
                    email=email,
                    bio=bio,
                    photo=photo_file,
                    photo_url=photo_url_val,
                    is_available=is_avail
                )
                # Create standard default schedules (Mon-Fri)
                for day_idx in range(5):
                    DoctorSchedule.objects.get_or_create(
                        doctor=new_doc,
                        day_of_week=day_idx,
                        defaults={'start_time': '09:00', 'end_time': '14:00', 'slot_duration': 15}
                    )
                messages.success(request, f'Dr. {name} registered successfully with default duty schedule.')
                return redirect('doctors:list')

    return render(request, 'doctors/list.html', {
        'doctors': doctors,
        'specialties': specialties,
        'clinic': clinic,
        'search': search,
        'specialty_filter': specialty_filter,
        'status_filter': status_filter,
        'view_mode': view_mode,
        'total_doctors': total_doctors,
        'available_doctors': available_doctors,
        'specialties_count': specialties_count,
        'avg_fee': avg_fee,
        'can_manage': can_manage,
    })


# API Viewset
class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.all().select_related('specialty')
    serializer_class = DoctorSerializer
