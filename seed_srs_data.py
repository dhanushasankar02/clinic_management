import os
import django
from decimal import Decimal
from datetime import date, timedelta, time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from apps.clinics.models import Clinic
from apps.doctors.models import Doctor, Specialty
from apps.patients.models import Patient
from apps.appointments.models import Appointment
from apps.consultations.models import Consultation, PrescriptionItem
from apps.laboratory.models import LabTest, LabOrder, LabOrderItem
from apps.pharmacy.models import Medicine, MedicineBatch, DispenseRecord, DispenseItem
from apps.billing.models import Service, Invoice, InvoiceItem, Payment

print("Seeding SRS Comprehensive Demo Data...")

clinic = Clinic.objects.first()
if not clinic:
    clinic = Clinic.objects.create(
        name="GrowwPark Apex Clinic & Diagnostics",
        slug="growwpark-apex-clinic",
        phone="+91 98765 43210",
        email="care@growwparkclinic.com",
        address="Tower 4, Healthcare Square, Central Avenue",
        city="Bengaluru",
        whatsapp_number="+91 98765 43210"
    )

# 1. Update existing patients with Patient ID / MRN if empty
patients = list(Patient.objects.all())
for idx, p in enumerate(patients, start=1001):
    if not p.patient_id:
        p.patient_id = f"PAT-{idx}"
        p.emergency_contact_name = "Family Member"
        p.emergency_contact_phone = "+91 98111 00000"
        p.save()

# Ensure we have at least 5 rich patients
if len(patients) < 3:
    p1 = Patient.objects.create(
        clinic=clinic,
        first_name="Rahul",
        last_name="Verma",
        phone="+91 98111 22334",
        email="rahul.verma@example.com",
        date_of_birth=date(1990, 5, 14),
        gender="M",
        blood_group="B+",
        address="Flat 402, Green Glen Layout, Bengaluru",
        emergency_contact_name="Pooja Verma",
        emergency_contact_phone="+91 98111 22335",
        allergies="Penicillin, Sulfa drugs",
        chronic_conditions="Mild Hypertension",
        medical_notes="Regular checkups"
    )
    patients.append(p1)

doc1 = Doctor.objects.first()
today = date.today()

# 2. Seed Services
services_data = [
    ("General Doctor Consultation", "SRV-CONS-01", "CONSULTATION", Decimal('500.00'), "Standard 15 min physician consultation"),
    ("Specialist Doctor Consultation", "SRV-CONS-02", "CONSULTATION", Decimal('800.00'), "Cardiology / Orthopedics consultation"),
    ("Wound Dressing & Suturing", "SRV-PROC-01", "PROCEDURE", Decimal('350.00'), "Antiseptic dressing and minor wound care"),
    ("12-Lead Electrocardiogram (ECG)", "SRV-PROC-02", "PROCEDURE", Decimal('450.00'), "Resting standard diagnostic ECG"),
    ("Emergency Triage / Day Care", "SRV-NURS-01", "NURSING", Decimal('600.00'), "IV infusion and 2-hour observation"),
]

for name, code, cat, fee, desc in services_data:
    Service.objects.get_or_create(
        code=code,
        defaults={
            'clinic': clinic,
            'name': name,
            'category': cat,
            'fee': fee,
            'description': desc
        }
    )

# 3. Seed Lab Tests
lab_tests_data = [
    ("Complete Blood Count (CBC)", "LAB-CBC", "HEMATOLOGY", "Whole Blood (EDTA)", "Hb: 13.5 - 17.5 g/dL, WBC: 4,000 - 11,000 /uL, Plt: 1.5 - 4.5 Lakhs", "g/dL", Decimal('350.00')),
    ("Fasting Blood Sugar (FBS)", "LAB-FBS", "BIOCHEMISTRY", "Sodium Fluoride Plasma", "70 - 99 mg/dL", "mg/dL", Decimal('150.00')),
    ("Glycated Hemoglobin (HbA1c)", "LAB-HBA1C", "BIOCHEMISTRY", "Whole Blood (EDTA)", "< 5.7 % (Normal), 5.7 - 6.4 % (Prediabetes)", "%", Decimal('550.00')),
    ("Lipid Profile Comprehensive", "LAB-LIPID", "BIOCHEMISTRY", "Serum", "Total Chol: < 200, HDL: > 40, LDL: < 100, Triglycerides: < 150", "mg/dL", Decimal('700.00')),
    ("Thyroid Stimulating Hormone (TSH)", "LAB-TSH", "BIOCHEMISTRY", "Serum", "0.45 - 4.50 uIU/mL", "uIU/mL", Decimal('300.00')),
    ("Routine Urine Examination", "LAB-URINE", "URINE", "Spot Urine", "Clear, Protein: Nil, Sugar: Nil, Pus cells: 1-2 /hpf", "-", Decimal('200.00')),
    ("Chest X-Ray PA View", "LAB-CXR", "RADIOLOGY", "Digital Radiography", "Normal bronchovascular markings, no active lesion", "-", Decimal('500.00')),
]

for name, code, cat, sample, norm, unit, price in lab_tests_data:
    LabTest.objects.get_or_create(
        code=code,
        defaults={
            'name': name,
            'category': cat,
            'sample_type': sample,
            'normal_range': norm,
            'unit': unit,
            'price': price,
            'description': f"Standard diagnostic lab panel: {name}"
        }
    )

# 4. Seed Pharmacy Medicines & Batches
medicines_data = [
    ("Dolo 650", "Paracetamol", "ANALGESIC", "TABLET", "650mg", Decimal('3.50'), 50, "BAT-DL26A", date(2027, 8, 30), 200),
    ("Augmentin 625 Duo", "Amoxicillin + Clavulanic Acid", "ANTIBIOTIC", "TABLET", "625mg", Decimal('22.00'), 30, "BAT-AUG26", date(2027, 4, 15), 120),
    ("Pantocid 40", "Pantoprazole", "GASTRO", "TABLET", "40mg", Decimal('11.50'), 40, "BAT-PAN26", date(2027, 11, 20), 150),
    ("Cetirizine 10", "Cetirizine Hydrochloride", "ANTIHISTAMINE", "TABLET", "10mg", Decimal('4.00'), 40, "BAT-CET26", date(2028, 1, 10), 180),
    ("Azithral 500", "Azithromycin", "ANTIBIOTIC", "TABLET", "500mg", Decimal('25.00'), 25, "BAT-AZI26", date(2026, 12, 31), 80),
    ("Glycomet 500 SR", "Metformin Hydrochloride", "ANTIDIABETIC", "TABLET", "500mg", Decimal('4.50'), 60, "BAT-GLY26", date(2027, 10, 15), 250),
    ("Telma 40", "Telmisartan", "ANTIHYPERTENSIVE", "TABLET", "40mg", Decimal('9.00'), 40, "BAT-TEL26", date(2027, 7, 25), 140),
    ("Ascoril LS Syrup", "Levosalbutamol + Ambroxol + Guaiphenesin", "RESPIRATORY", "SYRUP", "100ml", Decimal('115.00'), 15, "BAT-ASC26", date(2027, 5, 30), 45),
    ("Becosules Z", "B-Complex + Vitamin C + Zinc", "VITAMIN", "CAPSULE", "Standard", Decimal('5.00'), 50, "BAT-BEC26", date(2028, 3, 1), 300),
    ("Combiflam", "Ibuprofen + Paracetamol", "ANALGESIC", "TABLET", "400mg + 325mg", Decimal('4.80'), 50, "BAT-CMB26", date(2027, 9, 10), 160),
]

for name, generic, cat, form, strn, price, reorder, batch_no, exp, qty in medicines_data:
    med, _ = Medicine.objects.get_or_create(
        clinic=clinic,
        name=name,
        defaults={
            'generic_name': generic,
            'category': cat,
            'dosage_form': form,
            'strength': strn,
            'unit_price': price,
            'reorder_level': reorder
        }
    )
    MedicineBatch.objects.get_or_create(
        medicine=med,
        batch_number=batch_no,
        defaults={
            'expiry_date': exp,
            'quantity_in_stock': qty,
            'purchase_price': price * Decimal('0.7'),
            'selling_price': price,
            'supplier': "MedSource Pharma Distributors"
        }
    )

# 5. Seed a Sample Consultation with Prescriptions and Vitals
if patients and doc1:
    p = patients[0]
    consult, created = Consultation.objects.get_or_create(
        patient=p,
        doctor=doc1,
        defaults={
            'temperature': Decimal('99.2'),
            'pulse': 78,
            'blood_pressure': '124/82',
            'respiratory_rate': 18,
            'spo2': 98,
            'height_cm': Decimal('174.0'),
            'weight_kg': Decimal('72.5'),
            'chief_complaints': 'Fever for 2 days associated with mild throat irritation and dry cough.',
            'examination_notes': 'Pharynx mildly congested. Chest clear bilaterally, normal breath sounds. No cervical lymphadenopathy.',
            'diagnosis': 'Acute Upper Respiratory Tract Infection (URTI) with mild fever',
            'treatment_plan': 'Adequate hydration, warm saline gargles, antipyretics and short antihistamine course.',
            'clinical_notes': 'Advised to report immediately if breathing difficulty occurs or fever exceeds 102 F.',
            'follow_up_date': today + timedelta(days=5)
        }
    )
    if created:
        PrescriptionItem.objects.create(
            consultation=consult,
            medicine_name="Dolo 650",
            dosage="1 tablet",
            route="Oral",
            frequency="1-0-1",
            duration_days=3,
            instructions="After meals as needed for fever"
        )
        PrescriptionItem.objects.create(
            consultation=consult,
            medicine_name="Cetirizine 10",
            dosage="1 tablet",
            route="Oral",
            frequency="0-0-1",
            duration_days=5,
            instructions="At bedtime"
        )
        PrescriptionItem.objects.create(
            consultation=consult,
            medicine_name="Ascoril LS Syrup",
            dosage="10 ml",
            route="Oral",
            frequency="1-1-1",
            duration_days=5,
            instructions="After meals for dry cough"
        )

    # 6. Seed Sample Lab Order
    cbc_test = LabTest.objects.filter(code='LAB-CBC').first()
    fbs_test = LabTest.objects.filter(code='LAB-FBS').first()
    if cbc_test and fbs_test:
        order, _ = LabOrder.objects.get_or_create(
            clinic=clinic,
            patient=p,
            doctor=doc1,
            consultation=consult,
            defaults={
                'priority': 'ROUTINE',
                'status': 'COMPLETED',
                'clinical_notes': 'Evaluation of acute viral syndrome vs bacterial infection'
            }
        )
        if not order.items.exists():
            LabOrderItem.objects.create(
                order=order,
                test=cbc_test,
                result_value="14.2 g/dL (Hb) | WBC: 7,400 /uL | Platelets: 2.4 Lakhs",
                flag="NORMAL",
                technician_remarks="Cell morphology within normal limits.",
                is_verified=True,
                verified_by="Dr. Meera Pathologist"
            )
            LabOrderItem.objects.create(
                order=order,
                test=fbs_test,
                result_value="92 mg/dL",
                flag="NORMAL",
                technician_remarks="Fasting 10 hours confirmed.",
                is_verified=True,
                verified_by="Dr. Meera Pathologist"
            )

    # 7. Seed Sample Invoice & Payment
    inv, inv_created = Invoice.objects.get_or_create(
        clinic=clinic,
        patient=p,
        doctor=doc1,
        consultation=consult,
        defaults={
            'discount': Decimal('50.00'),
            'tax_percent': Decimal('0.00'),
            'status': 'PAID',
            'due_date': today,
            'notes': 'Consultation & routine lab testing package'
        }
    )
    if inv_created:
        InvoiceItem.objects.create(
            invoice=inv,
            item_type='CONSULTATION',
            description=f"Consultation Fee - Dr. {doc1.name}",
            quantity=1,
            unit_price=Decimal('500.00')
        )
        InvoiceItem.objects.create(
            invoice=inv,
            item_type='LAB',
            description="Complete Blood Count (CBC) Diagnostic Test",
            quantity=1,
            unit_price=Decimal('350.00')
        )
        InvoiceItem.objects.create(
            invoice=inv,
            item_type='PHARMACY',
            description="Pharmacy Medicines (Dolo 650, Cetirizine 10)",
            quantity=1,
            unit_price=Decimal('120.00')
        )
        inv.recalculate()

        Payment.objects.create(
            invoice=inv,
            amount=inv.total_amount,
            payment_method='UPI',
            transaction_reference='UPI-PAY-882374921',
            received_by='Accounts Desk',
            notes='Paid via Google Pay'
        )
        inv.recalculate()

print("Seeding Complete Successfully!")
