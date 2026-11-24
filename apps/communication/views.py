import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from apps.communication.models import WhatsAppConversation, WhatsAppMessage
from apps.clinics.models import Clinic
from apps.chatbot.engine import ChatbotEngine
from integrations.whatsapp.client import WhatsAppClient
from django.contrib.auth.decorators import login_required

@login_required
def inbox_view(request):
    clinic = Clinic.objects.first()
    conversations = WhatsAppConversation.objects.filter(clinic=clinic).select_related('patient')
    active_id = request.GET.get('chat')
    active_chat = None
    messages_list = []

    if active_id:
        active_chat = get_object_or_404(WhatsAppConversation, id=active_id, clinic=clinic)
    elif conversations.exists():
        active_chat = conversations.first()

    if active_chat:
        messages_list = active_chat.messages.all().order_by('created_at')

    return render(request, 'communication/inbox.html', {
        'clinic': clinic,
        'conversations': conversations,
        'active_chat': active_chat,
        'messages_list': messages_list
    })

def send_agent_message(request, chat_id):
    if request.method == 'POST':
        clinic = Clinic.objects.first()
        chat = get_object_or_404(WhatsAppConversation, id=chat_id, clinic=clinic)

        # Parse text from JSON body or standard form POST
        text = ''
        sender_mode = 'AGENT'  # 'AGENT' or 'PATIENT'

        if request.content_type == 'application/json' or (request.body and request.body.startswith(b'{')):
            try:
                payload = json.loads(request.body.decode('utf-8'))
                text = payload.get('text', '').strip()
                sender_mode = payload.get('mode', 'PATIENT')
            except Exception:
                pass

        if not text:
            text = request.POST.get('text', '').strip()
            sender_mode = request.POST.get('mode', 'PATIENT')

        reply_text = None

        if text and clinic:
            engine = ChatbotEngine(clinic)
            if sender_mode == 'PATIENT' or chat.status == 'BOT':
                # Process as incoming patient message -> triggers instant bot reply!
                patient_name = chat.patient.full_name if chat.patient else 'Patient'
                reply_text = engine.process_incoming_message(chat.phone_number, text, patient_name)
            else:
                # Direct staff response
                WhatsAppMessage.objects.create(
                    conversation=chat,
                    sender='AGENT',
                    text=text
                )
                chat.last_message = text
                chat.save()

                # Dispatch via WhatsApp API wrapper (if configured)
                client = WhatsAppClient()
                client.send_text_message(chat.phone_number, text)

        # If AJAX/Fetch request, return JSON response for instant UI update
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json'
        if is_ajax:
            return JsonResponse({
                'status': 'success',
                'user_text': text,
                'bot_reply': reply_text,
                'chat_id': chat_id
            })

        return redirect(f"/communication/?chat={chat_id}")

    return redirect('communication:inbox')

@csrf_exempt
def whatsapp_webhook(request):
    """Webhook for Meta WhatsApp Cloud API verification and message reception."""
    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        if mode == 'subscribe' and token:
            return HttpResponse(challenge, status=200)
        return HttpResponse('Verification failed', status=403)

    elif request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            clinic = Clinic.objects.first()
            if not clinic:
                return JsonResponse({'status': 'no_clinic'})

            engine = ChatbotEngine(clinic)
            entries = data.get('entry', [])
            for entry in entries:
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    contacts = value.get('contacts', [])
                    sender_name = contacts[0].get('profile', {}).get('name') if contacts else None
                    messages = value.get('messages', [])
                    for msg in messages:
                        from_number = msg.get('from')
                        text = msg.get('text', {}).get('body')
                        if from_number and text:
                            engine.process_incoming_message(from_number, text, sender_name)
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return HttpResponse(status=405)


@login_required
def notifications_view(request):
    """Staff/Doctor dedicated notifications inbox. Only shows alerts for the logged-in user."""
    from apps.appointments.models import AppointmentNotification
    notifications = AppointmentNotification.objects.filter(user=request.user).select_related('appointment', 'appointment__patient', 'appointment__doctor').order_by('-created_at')
    unread_count = notifications.filter(is_read=False).count()
    AppointmentNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return render(request, 'communication/notifications.html', {
        'notifications': notifications,
        'unread_count': unread_count,
    })


@login_required
def notification_mark_read(request, pk):
    from apps.appointments.models import AppointmentNotification
    notif = get_object_or_404(AppointmentNotification, pk=pk, user=request.user)
    notif.is_read = True
    notif.save()
    return redirect('communication:notifications')
