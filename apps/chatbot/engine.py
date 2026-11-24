import re
from datetime import date, datetime, timedelta
from django.utils import timezone
from apps.doctors.models import Doctor
from apps.patients.models import Patient
from apps.appointments.models import Appointment, notify_doctor_appointment
from apps.communication.models import WhatsAppConversation, WhatsAppMessage
from apps.chatbot.models import BotIntent, ClinicFAQ
from integrations.ai.client import AIClient

def _has_word(text, words):
    """Checks if any word/phrase from the list exists as a distinct token or phrase in text."""
    pattern = r'\b(' + '|'.join(re.escape(w) for w in words) + r')\b'
    return bool(re.search(pattern, text, re.IGNORECASE))

class ChatbotEngine:
    """Intelligent automated assistant for patient inquiries, schedules, and instant booking."""

    def __init__(self, clinic):
        self.clinic = clinic
        self.ai_client = AIClient()

    def _get_location_text(self):
        """Constructs a clean, complete location address string for the clinic."""
        parts = []
        if self.clinic.name:
            parts.append(self.clinic.name)
        if self.clinic.address:
            parts.append(self.clinic.address)
        if self.clinic.city:
            parts.append(self.clinic.city)
        return ", ".join(parts) if parts else (self.clinic.address or self.clinic.name or "Apex Multi-Specialty Clinic")

    def _build_clinic_context(self):
        """Builds structured clinic context for AI responses."""
        doctors = Doctor.objects.filter(clinic=self.clinic, is_available=True).select_related('specialty')
        doc_list = []
        for d in doctors:
            spec = d.specialty.name if d.specialty else 'General Medicine'
            doc_list.append(f"Dr. {d.name} ({spec}, Fee: ₹{d.consultation_fee}, Exp: {d.experience_years} yrs)")

        faqs = ClinicFAQ.objects.filter(clinic=self.clinic, is_active=True)
        faq_list = [f"Q: {f.question} | A: {f.answer}" for f in faqs]

        return (
            f"Clinic Name: {self.clinic.name}\n"
            f"Address: {self._get_location_text()}\n"
            f"Phone: {self.clinic.phone}\n"
            f"Working Hours: Monday to Saturday 09:00 AM - 08:00 PM. Emergency 24/7.\n"
            f"Available Doctors: {'; '.join(doc_list)}\n"
            f"Clinic FAQs: {'; '.join(faq_list)}"
        )

    def _get_patient_details_card(self, patient, prefix=""):
        """Constructs a clean, complete patient profile card."""
        active_appts = Appointment.objects.filter(
            patient=patient,
            appointment_date__gte=date.today(),
            status__in=['CONFIRMED', 'PENDING']
        ).count()

        gender_display = patient.get_gender_display() if hasattr(patient, 'get_gender_display') else patient.gender
        bg_display = patient.blood_group if patient.blood_group and patient.blood_group != 'UNKNOWN' else 'Not Specified'
        allergies_display = patient.allergies if patient.allergies else 'None reported'
        email_display = patient.email if patient.email else 'Not provided'
        address_display = patient.address if patient.address else 'On file'

        header = prefix or "👤 *Full Patient Details:*"
        return (
            f"{header}\n\n"
            f"• *Name:* {patient.full_name}\n"
            f"• *WhatsApp / Phone:* {patient.phone}\n"
            f"• *Email:* {email_display}\n"
            f"• *Gender:* {gender_display}\n"
            f"• *Blood Group:* {bg_display}\n"
            f"• *Allergies:* {allergies_display}\n"
            f"• *Address:* {address_display}\n"
            f"• *Active Appointments:* {active_appts}\n\n"
            f"👉 Reply *My Appointments* to check your visit schedule or *Book* to schedule a new visit."
        )

    def _format_appointment_details(self, appt, prefix=""):
        """Constructs a complete, detailed appointment confirmation card."""
        doc = appt.doctor
        spec = doc.specialty.name if doc.specialty else 'General Medicine'
        location_str = self._get_location_text()
        time_display = appt.appointment_time.strftime('%I:%M %p') if hasattr(appt.appointment_time, 'strftime') else str(appt.appointment_time)
        date_display = appt.appointment_date.strftime('%A, %d %b %Y') if hasattr(appt.appointment_date, 'strftime') else str(appt.appointment_date)
        reason_str = appt.reason or 'General Consultation'
        status_str = appt.get_status_display()
        header = prefix or "📋 *Booked Appointment Details:*"

        email_line = f"📧 *Email:* {appt.patient.email}\n" if appt.patient.email else ""

        return (
            f"{header}\n\n"
            f"👤 *Patient Name:* {appt.patient.full_name}\n"
            f"📱 *Phone:* {appt.patient.phone}\n"
            f"{email_line}"
            f"🩺 *Doctor:* Dr. {doc.name} ({spec})\n"
            f"📅 *Date:* {date_display}\n"
            f"⏰ *Time:* {time_display}\n"
            f"📍 *Location:* {location_str}\n"
            f"💵 *Consultation Fee:* ₹{doc.consultation_fee}\n"
            f"📌 *Status:* {status_str}\n"
            f"📝 *Reason for Visit:* {reason_str}\n\n"
            f"👉 Reply *Cancel* if you need to cancel this visit, or *Book* to schedule a new one."
        )

    def _match_doctor(self, text):
        """Intelligently matches a doctor by name or specialty keywords, defaulting gracefully."""
        doctors = Doctor.objects.filter(clinic=self.clinic, is_available=True).select_related('specialty')
        if not doctors.exists():
            doctors = Doctor.objects.filter(clinic=self.clinic).select_related('specialty')

        text_lower = text.lower()
        # 1. Match doctor name directly
        for doc in doctors:
            name_parts = [p.lower() for p in doc.name.split() if len(p) > 2]
            if any(re.search(r'\b' + re.escape(p) + r'\b', text_lower) for p in name_parts):
                return doc

        # 2. Match specialty keywords
        if _has_word(text_lower, ['heart', 'cardio', 'cardiac', 'hypertension', 'blood pressure']):
            d = doctors.filter(specialty__name__icontains='cardio').first()
            if d: return d
        if _has_word(text_lower, ['skin', 'derma', 'allergy', 'rash', 'acne', 'pimple']):
            d = doctors.filter(specialty__name__icontains='derma').first()
            if d: return d
        if _has_word(text_lower, ['child', 'pediatric', 'kid', 'baby', 'infant', 'vaccine', 'vaccination']):
            d = doctors.filter(specialty__name__icontains='pediatric').first()
            if d: return d
        if _has_word(text_lower, ['general', 'physician', 'fever', 'cold', 'cough', 'flu', 'headache', 'body pain']):
            d = doctors.filter(specialty__name__icontains='general').first()
            if d: return d

        # 3. Default to General Medicine or first available doctor
        return doctors.filter(specialty__name__icontains='general').first() or doctors.first()

    def _parse_datetime(self, text):
        """Extracts date and time from user query, or selects convenient next slot."""
        text_lower = text.lower()
        today = date.today()

        # Parse date
        booking_date = today + timedelta(days=1)
        if 'today' in text_lower:
            booking_date = today
        elif 'tomorrow' in text_lower:
            booking_date = today + timedelta(days=1)
        else:
            weekdays = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }
            for day_name, day_num in weekdays.items():
                if day_name in text_lower:
                    days_ahead = (day_num - today.weekday() + 7) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    booking_date = today + timedelta(days=days_ahead)
                    break

        # Parse time
        time_str = "10:00:00"
        display_time = "10:00 AM"

        time_match = re.search(r'(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)', text_lower)
        if time_match:
            hr = int(time_match.group(1))
            mn = int(time_match.group(2) or 0)
            ampm = time_match.group(3)
            if ampm == 'pm' and hr < 12:
                hr += 12
            elif ampm == 'am' and hr == 12:
                hr = 0
            time_str = f"{hr:02d}:{mn:02d}:00"
            try:
                dt_obj = datetime.strptime(time_str, "%H:%M:%S")
                display_time = dt_obj.strftime("%I:%M %p")
            except Exception:
                display_time = f"{hr:02d}:{mn:02d}"
        elif 'morning' in text_lower:
            time_str = "10:00:00"
            display_time = "10:00 AM"
        elif 'afternoon' in text_lower:
            time_str = "14:00:00"
            display_time = "02:00 PM"
        elif 'evening' in text_lower:
            time_str = "17:00:00"
            display_time = "05:00 PM"

        return booking_date, time_str, display_time

    def process_incoming_message(self, phone_number, incoming_text, sender_name=None):
        """Processes an incoming message from a phone number and generates an instant, strictly relevant reply."""
        text = (incoming_text or '').strip()
        if not text:
            return "Please type a message to get started."

        cleaned = text.lower()

        # Find or create conversation
        conversation, _ = WhatsAppConversation.objects.get_or_create(
            clinic=self.clinic,
            phone_number=phone_number,
            defaults={'status': 'BOT'}
        )

        # Find or create patient guaranteed
        patient = Patient.objects.filter(clinic=self.clinic, phone=phone_number).first()
        if not patient:
            name_parts = (sender_name or 'Patient').strip().split(' ', 1)
            first_name = name_parts[0] if name_parts else 'Patient'
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            patient = Patient.objects.create(
                clinic=self.clinic,
                first_name=first_name,
                last_name=last_name,
                phone=phone_number,
                gender='M',
                blood_group='UNKNOWN'
            )

        if not conversation.patient:
            conversation.patient = patient
            conversation.save(update_fields=['patient'])

        # Store inbound patient message
        WhatsAppMessage.objects.create(
            conversation=conversation,
            sender='PATIENT',
            text=text
        )

        # Reset back to BOT mode if patient sends reset keywords
        reset_keywords = ['bot', 'menu', 'reset', 'restart']
        if conversation.status == 'AGENT' and _has_word(cleaned, reset_keywords):
            conversation.status = 'BOT'
            conversation.save(update_fields=['status'])

        # If currently in AGENT mode (active human handoff)
        if conversation.status == 'AGENT':
            reply_text = (
                "🛎️ Your conversation is currently assigned to our clinic reception team.\n\n"
                "A human staff member will assist you shortly.\n"
                "👉 To resume automated assistance anytime, reply *Bot*."
            )
        else:
            # Generate instant, direct, topic-specific response
            reply_text = self._generate_response(cleaned, patient, conversation, raw_text=text)

        # Store outbound bot reply
        WhatsAppMessage.objects.create(
            conversation=conversation,
            sender='BOT',
            text=reply_text
        )

        conversation.last_message = reply_text
        conversation.save(update_fields=['last_message', 'last_message_at'])

        return reply_text

    def _generate_response(self, text, patient, conversation, raw_text=""):
        """Generates a direct, strictly relevant reply answering only what the user asked."""

        # Resolve target patient if specific phone number or registered patient name is mentioned
        target_patient = patient
        phone_match = re.search(r'(?:\+?91[\s-]?)?([6-9]\d{9})', text)
        if phone_match:
            found = Patient.objects.filter(clinic=self.clinic, phone__icontains=phone_match.group(1)).first()
            if found:
                target_patient = found
        else:
            for p in Patient.objects.filter(clinic=self.clinic):
                if len(p.first_name) >= 3 and _has_word(text, [p.first_name.lower()]):
                    target_patient = p
                    break

        # ---------------------------------------------------------
        # 1. CANCEL APPOINTMENT
        # ---------------------------------------------------------
        if text == '4' or _has_word(text, ['cancel', 'cancellation', 'cancel appointment', 'cancel visit']):
            latest_appt = Appointment.objects.filter(
                patient=target_patient,
                appointment_date__gte=date.today(),
                status__in=['CONFIRMED', 'PENDING']
            ).order_by('appointment_date').first()

            if latest_appt:
                latest_appt.status = 'CANCELLED'
                latest_appt.cancellation_reason = 'Cancelled by patient via WhatsApp Bot'
                latest_appt.save(update_fields=['status', 'cancellation_reason'])
                return (
                    f"🚫 *Appointment Cancelled*\n\n"
                    f"Your appointment with Dr. {latest_appt.doctor.name} on {latest_appt.appointment_date.strftime('%d %b %Y')} has been cancelled successfully.\n\n"
                    f"👉 Reply *Book* whenever you wish to reschedule a visit."
                )
            else:
                return "You currently have no active upcoming appointments to cancel. Reply *Book* to schedule a new visit."

        # ---------------------------------------------------------
        # 2. CHECK STATUS / ALREADY BOOKED APPOINTMENT DETAILS
        # ---------------------------------------------------------
        check_appointment_triggers = [
            'my appointment', 'my appointments', 'appointment status', 'check appointment',
            'my visits', 'my visit', 'when is my visit', 'when is my appointment',
            'already booked', 'i already booked', 'i have booked', 'i booked',
            'my booking', 'my bookings', 'booking details', 'booked details',
            'check booking', 'check my booking', 'show booking', 'show my booking',
            'appointment details', 'show appointment', 'booked appointment',
            'what is my appointment', 'do i have an appointment', 'check visit'
        ]
        is_check_appointment = (
            text == '3' or
            any(t in text for t in check_appointment_triggers) or
            (_has_word(text, ['booked', 'booking', 'appointment', 'visit']) and _has_word(text, ['already', 'my', 'details', 'detail', 'status', 'check', 'show', 'view', 'what', 'when', 'existing']))
        )
        if is_check_appointment:
            upcoming = Appointment.objects.filter(
                patient=target_patient,
                appointment_date__gte=date.today(),
                status__in=['CONFIRMED', 'PENDING', 'SCHEDULED', 'COMPLETED']
            ).select_related('doctor', 'doctor__specialty').order_by('appointment_date', 'appointment_time')

            if not upcoming.exists():
                any_appt = Appointment.objects.filter(patient=target_patient).select_related('doctor', 'doctor__specialty').order_by('-appointment_date', '-appointment_time').first()
                if any_appt:
                    return self._format_appointment_details(any_appt, prefix="📋 *Your Booked Appointment Details:*")
                return f"Hello {target_patient.full_name}, you currently have no appointments on record. Reply *Book* to schedule a visit."

            latest = upcoming.first()
            resp = self._format_appointment_details(latest, prefix="📋 *Your Booked Appointment Details:*")

            if upcoming.count() > 1:
                other_lines = ["\n*Other Active Appointments:*"]
                for a in upcoming[1:4]:
                    doc_s = a.doctor.specialty.name if a.doctor.specialty else 'General Medicine'
                    t_disp = a.appointment_time.strftime('%I:%M %p') if hasattr(a.appointment_time, 'strftime') else str(a.appointment_time)
                    d_disp = a.appointment_date.strftime('%d %b %Y') if hasattr(a.appointment_date, 'strftime') else str(a.appointment_date)
                    other_lines.append(f"• *Dr. {a.doctor.name}* ({doc_s}) on {d_disp} at {t_disp} ({a.get_status_display()})")
                resp += "\n" + "\n".join(other_lines)

            return resp

        # ---------------------------------------------------------
        # 3. PATIENT DETAILS (VIEW OR FILL/UPDATE)
        # ---------------------------------------------------------
        # Check if the user is filling/updating details (e.g., name, email, blood group, allergies)
        updated_any = False
        name_match = re.search(r'(?:my name is|name is|name:)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)', text, re.IGNORECASE)
        if name_match:
            new_name = name_match.group(1).strip().split(' ', 1)
            target_patient.first_name = new_name[0].title()
            target_patient.last_name = new_name[1].title() if len(new_name) > 1 else ''
            updated_any = True

        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', raw_text or text)
        if email_match:
            target_patient.email = email_match.group(0).strip()
            updated_any = True

        bg_match = re.search(r'\b(A\+|A-|B\+|B-|AB\+|AB-|O\+|O-)\b', text, re.IGNORECASE)
        if bg_match:
            target_patient.blood_group = bg_match.group(1).upper()
            updated_any = True

        allergy_match = re.search(r'(?:allergies|allergy)(?:\s+is|\s+are|:)?\s+([a-zA-Z0-9,\s]+)', text, re.IGNORECASE)
        if allergy_match and not _has_word(text, ['doctor', 'clinic', 'specialist', 'dr']):
            target_patient.allergies = allergy_match.group(1).strip()
            updated_any = True

        if updated_any:
            target_patient.save()
            return self._get_patient_details_card(target_patient, prefix="✅ *Patient details saved & updated successfully!*")

        patient_view_triggers = [
            'patient details', 'patient detail', 'my details', 'patient info', 'patient profile',
            'my profile', 'my info', 'full patient details', 'who am i', 'patient record',
            'patient records', 'medical profile', 'show patient details', 'view patient details'
        ]
        has_patient_query = (
            any(t in text for t in patient_view_triggers) or
            (_has_word(text, ['patient', 'my']) and _has_word(text, ['details', 'detail', 'info', 'profile', 'record', 'records', 'information']))
        )
        if has_patient_query:
            return self._get_patient_details_card(target_patient)

        # ---------------------------------------------------------
        # 4. HUMAN HANDOFF / RECEPTION
        # ---------------------------------------------------------
        if text == '6' or _has_word(text, ['human', 'reception', 'receptionist', 'coordinator', 'staff', 'operator', 'talk to person', 'speak with someone', 'call desk', 'agent', 'support']):
            conversation.status = 'AGENT'
            conversation.save(update_fields=['status'])
            return (
                "🛎️ *Transferred to Clinic Reception*\n\n"
                "I have routed this chat to our front desk team. A receptionist will assist you directly.\n\n"
                "👉 To resume automated assistance anytime, reply *Bot*."
            )

        # ---------------------------------------------------------
        # 4. INSTANT APPOINTMENT BOOKING
        # ---------------------------------------------------------
        booking_action_words = ['book', 'booking', 'reserve', 'schedule', 'appoint', 'slot']
        booking_explicit = [
            'ok doctor', 'ok doc', 'yes doctor', 'confirm doctor', 'need doctor',
            'see doctor', 'want doctor', 'doctor appointment', 'take appointment',
            'get appointment', 'fix appointment'
        ]

        has_booking_intent = (
            text == '2' or
            _has_word(text, booking_action_words) or
            any(p in text for p in booking_explicit)
        )

        # Do not book if user is checking an existing/already booked appointment
        if is_check_appointment or (_has_word(text, ['already', 'check', 'status', 'show', 'view']) and _has_word(text, ['booked', 'booking', 'appointment'])):
            has_booking_intent = False

        # Handle user confirming after doctor recommendation
        if not has_booking_intent and conversation.last_message:
            last_bot_msg = conversation.last_message.lower()
            if any(k in last_bot_msg for k in ['book', 'appointment', 'specialist', 'doctor']):
                if text in ['ok', 'yes', 'sure', 'confirm', 'proceed', 'please', 'ok please', 'done', 'yes please']:
                    has_booking_intent = True

        if has_booking_intent:
            matched_doctor = self._match_doctor(text)
            if not matched_doctor:
                return f"No doctors are currently available at {self.clinic.name}. Please contact reception."

            booking_date, time_str, display_time = self._parse_datetime(text)
            location_str = self._get_location_text()

            existing_appt = Appointment.objects.filter(
                clinic=self.clinic,
                doctor=matched_doctor,
                patient=patient,
                appointment_date=booking_date,
                appointment_time=time_str
            ).first()

            if not existing_appt:
                new_appt = Appointment.objects.create(
                    clinic=self.clinic,
                    doctor=matched_doctor,
                    patient=patient,
                    appointment_date=booking_date,
                    appointment_time=time_str,
                    source='WHATSAPP',
                    status='CONFIRMED',
                    reason='Booked via WhatsApp Assistant'
                )
                notify_doctor_appointment(new_appt, event_type='BOOKED')

            spec_name = matched_doctor.specialty.name if matched_doctor.specialty else 'General Medicine'

            return (
                f"✅ *Your appointment is confirmed!*\n\n"
                f"👤 *Patient Name:* {patient.full_name}\n"
                f"🩺 *Doctor:* Dr. {matched_doctor.name} ({spec_name})\n"
                f"📅 *Date:* {booking_date.strftime('%A, %d %b %Y')}\n"
                f"⏰ *Time:* {display_time}\n"
                f"📍 *Location:* {location_str}\n"
                f"💵 *Consultation Fee:* ₹{matched_doctor.consultation_fee}\n\n"
                f"👉 Reply *My Appointments* to view status or *Cancel* if you need to cancel."
            )

        # ---------------------------------------------------------
        # 5. CONSULTATION FEES / PRICING INQUIRIES
        # ---------------------------------------------------------
        fee_keywords = ['fee', 'fees', 'cost', 'costs', 'price', 'prices', 'pricing', 'charge', 'charges', 'rate', 'rates', 'how much']
        if _has_word(text, fee_keywords):
            doctors = Doctor.objects.filter(clinic=self.clinic, is_available=True).select_related('specialty')
            # Check if user asked about a specific doctor or specialty
            for doc in doctors:
                name_parts = [p.lower() for p in doc.name.split() if len(p) > 2]
                spec_name = doc.specialty.name.lower() if doc.specialty else ''
                if any(_has_word(text, [p]) for p in name_parts) or (spec_name and _has_word(text, [spec_name])):
                    spec = doc.specialty.name if doc.specialty else 'General Medicine'
                    return (
                        f"💵 *Consultation Fee for Dr. {doc.name}* ({spec}):\n"
                        f"*₹{doc.consultation_fee}*\n\n"
                        f"👉 Reply *Book Dr. {doc.name.split()[0]}* to reserve an appointment."
                    )

            # General fees list
            lines = [f"💵 *Consultation Fees at {self.clinic.name}:*\n"]
            for doc in doctors:
                spec = doc.specialty.name if doc.specialty else "General Medicine"
                lines.append(f"• *Dr. {doc.name}* ({spec}): ₹{doc.consultation_fee}")
            lines.append("\n👉 Reply *Book* followed by doctor name to schedule a visit.")
            return "\n".join(lines)

        # ---------------------------------------------------------
        # 6. CLINIC TIMINGS & WORKING HOURS
        # ---------------------------------------------------------
        timing_keywords = ['timing', 'timings', 'time', 'times', 'hours', 'working hours', 'open', 'opens', 'opening', 'close', 'closes', 'closing', 'schedule']
        if _has_word(text, timing_keywords) and not _has_word(text, ['appointment', 'book', 'slot']):
            return (
                f"🕒 *Working Hours for {self.clinic.name}:*\n"
                f"• Monday to Saturday: 09:00 AM – 08:00 PM\n"
                f"• Sunday: Emergency & Urgent Care Only\n"
                f"• Emergency Unit: Available 24/7\n\n"
                f"📞 Reception: {self.clinic.phone}\n"
                f"👉 Reply *Book* to schedule an appointment."
            )

        # ---------------------------------------------------------
        # 7. CLINIC LOCATION, ADDRESS & PARKING
        # ---------------------------------------------------------
        location_keywords = ['address', 'location', 'where', 'located', 'locate', 'direction', 'directions', 'landmark', 'reach', 'parking', 'map', 'place']
        if _has_word(text, location_keywords):
            location_str = self._get_location_text()
            return (
                f"📍 *Clinic Address & Location:*\n"
                f"*{self.clinic.name}*\n"
                f"{location_str}\n"
                f"📞 Phone: {self.clinic.phone}\n"
                f"🚗 Dedicated visitor & patient parking is available on-site.\n\n"
                f"👉 Reply *Book* to schedule your visit."
            )

        # ---------------------------------------------------------
        # 8. INSURANCE & PAYMENT MODES
        # ---------------------------------------------------------
        insurance_keywords = ['insurance', 'cashless', 'tpa', 'claim', 'claims', 'policy', 'mediclaim', 'payment', 'payments', 'pay online', 'upi', 'gpay', 'phonepe', 'card', 'credit card', 'debit card']
        if _has_word(text, insurance_keywords):
            return (
                f"💳 *Insurance & Payment Options:*\n"
                f"• We accept all major health insurance providers and TPA cashless claims.\n"
                f"• Accepted payment modes: UPI (Google Pay, PhonePe, Paytm), Debit/Credit Cards, Net Banking, and Cash.\n"
                f"• Receipts and claim forms are provided immediately after consultation.\n\n"
                f"👉 Reply *Book* to schedule an appointment."
            )

        # ---------------------------------------------------------
        # 9. EMERGENCY & URGENT CARE
        # ---------------------------------------------------------
        emergency_keywords = ['emergency', 'urgent', 'ambulance', 'critical', 'casualty', 'icu', 'accident']
        if _has_word(text, emergency_keywords):
            location_str = self._get_location_text()
            return (
                f"🚨 *24/7 Emergency Services:*\n"
                f"Our Emergency Care and Casualty unit is open 24/7 every day.\n"
                f"📞 *Immediate Hotline:* {self.clinic.phone}\n"
                f"📍 *Address:* {location_str}\n\n"
                f"Please proceed directly to our emergency triage counter for urgent treatment."
            )

        # ---------------------------------------------------------
        # 10. SYMPTOMS & MEDICAL TRIAGE GUIDANCE
        # ---------------------------------------------------------
        # Heart / Chest / BP
        if _has_word(text, ['chest pain', 'heart', 'cardiac', 'bp', 'blood pressure', 'hypertension', 'palpitation', 'breathless', 'cholesterol']):
            doc = Doctor.objects.filter(clinic=self.clinic, specialty__name__icontains='cardio', is_available=True).first()
            doc_name = f"Dr. {doc.name}" if doc else "our Senior Cardiologist"
            fee_str = f" (Fee: ₹{doc.consultation_fee})" if doc else ""
            return (
                f"🩺 For chest pain, blood pressure, or cardiovascular concerns, we recommend consulting {doc_name}{fee_str}.\n\n"
                f"👉 Reply *Book Dr. Arun* to schedule an appointment immediately."
            )

        # Skin / Dermatology / Allergy
        if _has_word(text, ['skin', 'rash', 'rashes', 'acne', 'pimple', 'pimples', 'allergy', 'allergies', 'itching', 'hair fall', 'hair loss', 'eczema', 'fungal']):
            doc = Doctor.objects.filter(clinic=self.clinic, specialty__name__icontains='derma', is_available=True).first()
            doc_name = f"Dr. {doc.name}" if doc else "our Dermatologist"
            fee_str = f" (Fee: ₹{doc.consultation_fee})" if doc else ""
            return (
                f"🩺 For skin, hair, or allergy concerns, we recommend consulting our Dermatologist {doc_name}{fee_str}.\n\n"
                f"👉 Reply *Book Dr. Priya* to schedule a consultation."
            )

        # Pediatrics / Child / Infant / Vaccination
        if _has_word(text, ['child', 'kid', 'kids', 'baby', 'babies', 'infant', 'newborn', 'pediatric', 'vaccine', 'vaccination']):
            doc = Doctor.objects.filter(clinic=self.clinic, specialty__name__icontains='pediatric', is_available=True).first()
            doc_name = f"Dr. {doc.name}" if doc else "our Pediatrician"
            fee_str = f" (Fee: ₹{doc.consultation_fee})" if doc else ""
            return (
                f"🩺 For infant & child health, milestone checks, or vaccinations, we recommend our Pediatrician {doc_name}{fee_str}.\n\n"
                f"👉 Reply *Book Dr. Vikram* to schedule an appointment."
            )

        # General Medicine / Fever / Cold / Cough / Headache / Stomach
        if _has_word(text, ['fever', 'cold', 'cough', 'flu', 'headache', 'stomach ache', 'stomach pain', 'vomiting', 'loose motion', 'diarrhea', 'body pain', 'throat', 'weakness', 'infection', 'dizzy']):
            doc = Doctor.objects.filter(clinic=self.clinic, specialty__name__icontains='general', is_available=True).first()
            doc_name = f"Dr. {doc.name}" if doc else "our General Physician"
            fee_str = f" (Fee: ₹{doc.consultation_fee})" if doc else ""
            return (
                f"🩺 For fever, cough, body pain, or general health concerns, we recommend consulting our General Physician {doc_name}{fee_str}.\n\n"
                f"👉 Reply *Book Dr. Sarah* to schedule an appointment."
            )

        # ---------------------------------------------------------
        # 11. DOCTOR INFORMATION & SPECIALIST LIST
        # ---------------------------------------------------------
        doctor_keywords = ['doctor', 'doctors', 'specialist', 'specialists', 'physician', 'cardiologist', 'dermatologist', 'pediatrician', 'dr']
        if text == '1' or _has_word(text, doctor_keywords):
            doctors = Doctor.objects.filter(clinic=self.clinic, is_available=True).select_related('specialty')

            # Check if specific doctor is requested
            for doc in doctors:
                name_parts = [p.lower() for p in doc.name.split() if len(p) > 2]
                spec_name = doc.specialty.name.lower() if doc.specialty else ''
                if any(_has_word(text, [p]) for p in name_parts) or (spec_name and _has_word(text, [spec_name]) and text != '1' and 'show' not in text and 'list' not in text):
                    spec = doc.specialty.name if doc.specialty else 'General Medicine'
                    return (
                        f"🩺 *Dr. {doc.name}*\n"
                        f"• Specialty: *{spec}*\n"
                        f"• Qualification: {doc.qualification}\n"
                        f"• Experience: {doc.experience_years} years\n"
                        f"• Consultation Fee: *₹{doc.consultation_fee}*\n"
                        f"• Availability: Monday to Friday (09:00 AM – 02:00 PM)\n\n"
                        f"👉 Reply *Book Dr. {doc.name.split()[0]}* to schedule an appointment."
                    )

            # General doctor catalog
            if not doctors.exists():
                return f"Currently no doctors are available at {self.clinic.name}. Please contact reception."

            lines = [f"🩺 *Available Doctors at {self.clinic.name}:*\n"]
            for idx, doc in enumerate(doctors, 1):
                spec = doc.specialty.name if doc.specialty else "General Medicine"
                lines.append(f"{idx}. *Dr. {doc.name}* ({spec}) - Fee: ₹{doc.consultation_fee}")
            lines.append("\n👉 Reply *Book* followed by doctor name to book (e.g. *Book Dr. Sarah*).")
            return "\n".join(lines)

        # ---------------------------------------------------------
        # 12. FAQ KNOWLEDGE BASE LOOKUP
        # ---------------------------------------------------------
        faqs = ClinicFAQ.objects.filter(clinic=self.clinic, is_active=True)
        cleaned_query_words = set(re.sub(r'[^\w\s]', '', text).split())
        for faq in faqs:
            q_clean = re.sub(r'[^\w\s]', '', faq.question.lower())
            q_words = set(w for w in q_clean.split() if len(w) > 3)
            # If at least 2 significant words match or significant subset overlap
            match_count = len(cleaned_query_words & q_words)
            if match_count >= 2 or (len(q_words) <= 2 and match_count >= 1):
                return f"💡 *{faq.question}*\n\n{faq.answer}"

        # ---------------------------------------------------------
        # 13. CONVERSATIONAL COURTESIES (GREETINGS, THANKS, BYE)
        # ---------------------------------------------------------
        # Greetings (concise, direct welcome - NO long menu dump!)
        greeting_words = ['hi', 'hello', 'hey', 'good morning', 'good evening', 'good afternoon', 'start', 'restart']
        if _has_word(text, greeting_words):
            return (
                f"Hello! Welcome to *{self.clinic.name}*! 👋\n\n"
                f"How can I assist you today? You can ask me about our doctors, consultation fees, clinic timings, or booking an appointment."
            )

        # Gratitude
        if _has_word(text, ['thank you', 'thanks', 'thx', 'thank u', 'appreciate', 'grateful']):
            return "You're very welcome! Let us know if you need any other assistance. Stay healthy! 🌟"

        # Acknowledgement
        if text in ['ok', 'okay', 'sure', 'alright', 'understood', 'got it', 'fine']:
            return "Understood! Please let me know if there is anything else you need."

        # Goodbyes
        if _has_word(text, ['bye', 'goodbye', 'see you', 'take care', 'good night']):
            return f"Goodbye and take care! *{self.clinic.name}* is always here whenever you need care. 👋"

        # ---------------------------------------------------------
        # 14. GENERATIVE AI DYNAMIC RESPONSE (If API Key is available)
        # ---------------------------------------------------------
        clinic_context = self._build_clinic_context()
        ai_reply = self.ai_client.generate_reply(raw_text or text, context=clinic_context)
        if ai_reply:
            return ai_reply

        # ---------------------------------------------------------
        # 15. CLEAN, DIRECT CLARIFICATION (Replaces the old rigid 5-bullet fallback)
        # ---------------------------------------------------------
        return (
            f"I am here to assist with your clinic visit, doctor consultations, fees, timings, and appointment bookings.\n\n"
            f"Could you please specify your question, or reply *Human* to speak directly with our reception desk?"
        )
