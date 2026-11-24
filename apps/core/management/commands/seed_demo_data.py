from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, timedelta, time
from apps.accounts.models import UserProfile
from apps.clinics.models import Clinic, ClinicSetting
from apps.doctors.models import Specialty, Doctor, DoctorSchedule
from apps.patients.models import Patient, MedicalRecord
from apps.appointments.models import Appointment
from apps.communication.models import WhatsAppConversation, WhatsAppMessage
from apps.chatbot.models import ClinicFAQ, BotIntent

class Command(BaseCommand):
    help = 'Seeds complete demonstration data for Smart Clinic Automation'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE('Starting demonstration data seeding...'))

        # 1. Superuser & Admin
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@apexclinic.com',
                'first_name': 'Dr. Robert',
                'last_name': 'Harris',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('Created default admin: admin / admin123'))

        # 2. Main Clinic
        clinic, _ = Clinic.objects.get_or_create(
            slug='apex-healthcare',
            defaults={
                'name': 'Apex Multi-Specialty Clinic',
                'phone': '+91 98765 43210',
                'email': 'care@apexclinic.com',
                'address': 'Plot 42, Health Avenue, Medical District',
                'city': 'Metro City',
                'whatsapp_number': '+91 98765 43210',
                'is_active': True
            }
        )
        ClinicSetting.objects.get_or_create(clinic=clinic)

        # Link admin profile
        UserProfile.objects.get_or_create(
            user=admin_user,
            defaults={'clinic': clinic, 'role': 'SUPER_ADMIN', 'phone': '+91 98765 43210'}
        )

        # 3. Specialties
        specs = [
            ('General Medicine', 'stethoscope', 'Primary comprehensive medical care'),
            ('Cardiology', 'heart-pulse', 'Cardiovascular disease, hypertension and heart health'),
            ('Dermatology', 'sparkles', 'Skin care, dermatology consultations, allergy treatment'),
            ('Pediatrics', 'baby', 'Children healthcare, vaccination and pediatric diagnostics'),
        ]
        spec_objs = {}
        for name, icon, desc in specs:
            sp, _ = Specialty.objects.get_or_create(
                slug=name.lower().replace(' ', '-'),
                defaults={'name': name, 'icon': icon, 'description': desc}
            )
            spec_objs[name] = sp

        # 4. Doctors
        doctors_data = [
            {
                'name': 'Sarah Jenkins',
                'specialty': spec_objs['General Medicine'],
                'qualification': 'MBBS, MD (Internal Medicine)',
                'experience_years': 9,
                'consultation_fee': 400.00,
                'phone': '+91 98765 00001',
                'email': 'dr.sarah@apexclinic.com',
                'bio': 'Passionate physician specializing in preventive healthcare and chronic illness management.'
            },
            {
                'name': 'Arun Sharma',
                'specialty': spec_objs['Cardiology'],
                'qualification': 'MBBS, MD, DM (Cardiology)',
                'experience_years': 14,
                'consultation_fee': 800.00,
                'phone': '+91 98765 00002',
                'email': 'dr.arun@apexclinic.com',
                'bio': 'Senior Interventional Cardiologist with extensive clinical expertise in cardiovascular medicine.'
            },
            {
                'name': 'Priya Nair',
                'specialty': spec_objs['Dermatology'],
                'qualification': 'MBBS, DVD, MD (Dermatology)',
                'experience_years': 7,
                'consultation_fee': 600.00,
                'phone': '+91 98765 00003',
                'email': 'dr.priya@apexclinic.com',
                'bio': 'Expert clinical and cosmetic dermatologist specializing in eczema, acne, and allergy care.'
            },
            {
                'name': 'Vikram Mehta',
                'specialty': spec_objs['Pediatrics'],
                'qualification': 'MBBS, DCH, MD (Pediatrics)',
                'experience_years': 11,
                'consultation_fee': 500.00,
                'phone': '+91 98765 00004',
                'email': 'dr.vikram@apexclinic.com',
                'bio': 'Dedicated pediatrician with special focus on infant nutrition, growth milestones, and pediatric care.'
            }
        ]

        created_docs = []
        for d_data in doctors_data:
            doc, _ = Doctor.objects.get_or_create(
                clinic=clinic,
                name=d_data['name'],
                defaults=d_data
            )
            created_docs.append(doc)

            # Create default schedules (Mon-Fri 09:00 - 14:00)
            for day in range(5):
                DoctorSchedule.objects.get_or_create(
                    doctor=doc,
                    day_of_week=day,
                    start_time=time(9, 0),
                    defaults={'end_time': time(14, 0), 'slot_duration': 20}
                )

        # 5. Patients
        patients_data = [
            ('Rahul', 'Verma', '+91 98111 22334', 'rahul.verma@example.com', 'M', 'O+', 'No known drug allergies'),
            ('Ananya', 'Deshmukh', '+91 98222 33445', 'ananya.d@example.com', 'F', 'B+', 'Mild penicillin allergy'),
            ('David', 'Miller', '+91 98333 44556', 'david.m@example.com', 'M', 'A+', 'Hypertension history'),
            ('Meera', 'Kapoor', '+91 98444 55667', 'meera.k@example.com', 'F', 'AB+', 'None'),
            ('Karan', 'Singhania', '+91 98555 66778', 'karan.s@example.com', 'M', 'O-', 'Asthma history'),
        ]

        created_patients = []
        for fname, lname, phone, email, gender, bg, notes in patients_data:
            p, _ = Patient.objects.get_or_create(
                clinic=clinic,
                phone=phone,
                defaults={
                    'first_name': fname,
                    'last_name': lname,
                    'email': email,
                    'gender': gender,
                    'blood_group': bg,
                    'allergies': notes,
                    'address': 'Metro City Central'
                }
            )
            created_patients.append(p)

        # 6. Appointments
        today = date.today()
        tomorrow = today + timedelta(days=1)
        day_after = today + timedelta(days=2)

        appointments_data = [
            (created_patients[0], created_docs[0], today, time(10, 0), 'CONFIRMED', 'WHATSAPP', 'Seasonal Flu & cough'),
            (created_patients[1], created_docs[1], today, time(11, 30), 'CONFIRMED', 'WEB', 'Annual cardiac checkup'),
            (created_patients[2], created_docs[2], today, time(12, 15), 'PENDING', 'WHATSAPP', 'Skin allergy on hands'),
            (created_patients[3], created_docs[3], tomorrow, time(9, 30), 'CONFIRMED', 'PHONE', 'Child 2-year vaccination'),
            (created_patients[4], created_docs[0], tomorrow, time(10, 45), 'SCHEDULED', 'WEB', 'Regular health checkup'),
            (created_patients[0], created_docs[2], day_after, time(15, 0), 'CONFIRMED', 'WHATSAPP', 'Follow-up consultation'),
        ]

        for pat, doc, adate, atime, stat, src, rsn in appointments_data:
            Appointment.objects.get_or_create(
                clinic=clinic,
                doctor=doc,
                patient=pat,
                appointment_date=adate,
                appointment_time=atime,
                defaults={'status': stat, 'source': src, 'reason': rsn}
            )

        # 7. WhatsApp Conversations & Messages
        conv, _ = WhatsAppConversation.objects.get_or_create(
            clinic=clinic,
            phone_number=patients_data[0][2],
            defaults={'patient': created_patients[0], 'status': 'BOT'}
        )
        WhatsAppMessage.objects.get_or_create(
            conversation=conv,
            text='Hi, I want to book an appointment with Dr. Sarah',
            defaults={'sender': 'PATIENT'}
        )
        WhatsAppMessage.objects.get_or_create(
            conversation=conv,
            text='Welcome to Apex Multi-Specialty Clinic! I found Dr. Sarah Jenkins (General Medicine). Slot booked for today at 10:00 AM.',
            defaults={'sender': 'BOT'}
        )

        # 8. FAQs
        faqs = [
            ("What are the clinic working hours?", "We are open Monday to Saturday, 9:00 AM to 8:00 PM. Emergency services are open 24/7."),
            ("Where is the clinic located?", "Plot 42, Health Avenue, Medical District, Metro City. Parking is available on-site."),
            ("What insurance plans do you accept?", "We accept all major health insurance providers, TPA cards, cashless claims, and digital payment methods."),
            ("How do I cancel or reschedule my appointment?", "You can simply message 'Cancel' or 'Reschedule' directly on WhatsApp at least 2 hours before your scheduled time.")
        ]
        for q, a in faqs:
            ClinicFAQ.objects.get_or_create(clinic=clinic, question=q, defaults={'answer': a})

        self.stdout.write(self.style.SUCCESS('Demo data seeding completed successfully!'))
