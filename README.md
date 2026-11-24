# 🏥 GrowwPark Smart Clinic Management & Hospital OS

A full-stack modular Django healthcare platform built strictly according to the **Software Requirements Specification (SRS)** for GrowwPark Technologies Private Limited.

---

## 🚀 Quick Start Guide

### 1. Start the Development Server
From this project directory (`F:\Django\venv\Scripts\clinic_management`):
```bash
F:\Django\venv\Scripts\python.exe manage.py runserver
```
Then open your browser to **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**.

### 2. Verify System Health Suite
Run the built-in 30-endpoint integration & verification test:
```bash
F:\Django\venv\Scripts\python.exe test_health.py
```

---

## 🔑 Default Credentials & Demo Data
The database (`db.sqlite3`) is pre-seeded with rich, realistic clinic data:
* **Admin Portal:** [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
* **Username:** `admin`
* **Password:** `admin123`

---

## 📋 SRS Modules Implemented

| Module | Web UI Route | REST API Endpoint | Key Capabilities |
| :--- | :--- | :--- | :--- |
| **Executive Dashboard** | `/` | — | Multi-department KPI cards (Queue, Collections, Lab, Pharmacy stock alerts, today's schedule). |
| **Reception & Token Queue** | `/appointments/queue/` | `/api/appointments/` | Live token queue display (T-01, T-02), instant check-in, printable visit slip. |
| **Appointments Manager** | `/appointments/` | `/api/appointments/` | Calendar & list views, doctor slot booking, walk-in support, status updates. |
| **Patients & Longitudinal EMR** | `/patients/` | `/api/patients/` | Auto-generated MRN IDs (`PAT-1001`), demographics, allergy alerts, chronic conditions, full visit history. |
| **Doctor Consultation & EMR** | `/consultations/` | `/api/consultations/`<br>`/api/prescriptions/` | Vitals with auto-BMI calculation, complaints, diagnosis, interactive Rx chart, printable prescription. |
| **Laboratory Management** | `/laboratory/`<br>`/laboratory/catalogue/` | `/api/lab-tests/`<br>`/api/lab-orders/` | Test catalogue, sample status tracking, result entry with normal ranges/abnormal flags, printable diagnostic lab report. |
| **Pharmacy & Inventory** | `/pharmacy/`<br>`/pharmacy/medicines/` | `/api/medicines/`<br>`/api/dispensations/` | Medicine catalogue, batch stock tracking, expiry alerts, prescription-based dispensing with auto stock deduction. |
| **Billing & Accounts** | `/billing/`<br>`/billing/services/` | `/api/services/`<br>`/api/invoices/`<br>`/api/payments/` | Invoice generation, discount & tax calculation, payment receipting (Cash, UPI, Card), outstanding tracking, printable invoice/receipt. |
| **Reports & Analytics** | `/reports/` | — | Daily/monthly collections, payment mode breakdown, doctor consultation productivity, lab & pharmacy stats. |
| **Doctors & Staff** | `/doctors/` | `/api/doctors/` | Profiles, specialties, consultation fees, on-duty schedules. |
| **WhatsApp AI Bot & Inbox** | `/communication/`<br>`/chatbot/test/` | `/communication/webhook/` | WhatsApp Web-style inbox + 24/7 automated appointment booking engine. |
| **Clinic Tenant Settings** | `/clinics/` | — | Facility profile, departments, working hours, and integration settings. |

---

## 🧪 Verified Test Suite
Running `python test_health.py` validates all **30 frontend screens, backend endpoints, and REST APIs**, along with the automated chatbot simulation:
```text
Executive Dashboard                 : /                         -> 200 [OK]
Appointments Manager                : /appointments/            -> 200 [OK]
Live Reception Queue                : /appointments/queue/      -> 200 [OK]
Doctors & Staff Directory           : /doctors/                 -> 200 [OK]
Patients Directory & EMR            : /patients/                -> 200 [OK]
Doctor Consultations & EMR          : /consultations/           -> 200 [OK]
Consultation Room Encounter         : /consultations/new/       -> 200 [OK]
Laboratory Investigation Queue      : /laboratory/              -> 200 [OK]
Diagnostic Test Master              : /laboratory/catalogue/    -> 200 [OK]
Pharmacy Stock & Expiry Dashboard   : /pharmacy/                -> 200 [OK]
Medicine Inventory Master           : /pharmacy/medicines/      -> 200 [OK]
Pharmacy Dispensations Log          : /pharmacy/dispense/       -> 200 [OK]
Invoices & Billing Manager          : /billing/                 -> 200 [OK]
Tariff & Service Catalogue          : /billing/services/        -> 200 [OK]
Clinical & Financial Reports        : /reports/                 -> 200 [OK]
WhatsApp Communications             : /communication/           -> 200 [OK]
AI Bot Simulator                    : /chatbot/test/            -> 200 [OK]
Clinic Settings                     : /clinics/                 -> 200 [OK]
API - Doctors                       : /api/doctors/             -> 200 [OK]
API - Patients                      : /api/patients/            -> 200 [OK]
API - Appointments                  : /api/appointments/        -> 200 [OK]
API - Consultations                 : /api/consultations/       -> 200 [OK]
API - Prescriptions                 : /api/prescriptions/       -> 200 [OK]
API - Lab Tests                     : /api/lab-tests/           -> 200 [OK]
API - Lab Orders                    : /api/lab-orders/          -> 200 [OK]
API - Medicines                     : /api/medicines/           -> 200 [OK]
API - Dispensations                 : /api/dispensations/       -> 200 [OK]
API - Services                      : /api/services/            -> 200 [OK]
API - Invoices                      : /api/invoices/            -> 200 [OK]
API - Payments                      : /api/payments/            -> 200 [OK]
```
