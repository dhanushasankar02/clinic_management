import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from apps.clinics.models import Clinic
from apps.patients.models import Patient
from apps.chatbot.models import ClinicFAQ, BotIntent
from apps.chatbot.engine import ChatbotEngine
from apps.communication.models import WhatsAppConversation
from django.contrib.auth.decorators import login_required

@login_required
def test_chatbot(request):
    clinic = Clinic.objects.first()
    faqs = ClinicFAQ.objects.filter(clinic=clinic) if clinic else []
    conversations = WhatsAppConversation.objects.filter(clinic=clinic).order_by('-last_message_at')[:10] if clinic else []
    patients = Patient.objects.filter(clinic=clinic).order_by('-id') if clinic else []
    return render(request, 'chatbot/test_chatbot.html', {
        'clinic': clinic,
        'faqs': faqs,
        'conversations': conversations,
        'patients': patients
    })

@csrf_exempt
def simulate_chat_api(request):
    """Processes simulated patient message and generates instant bot reply."""
    if request.method == 'POST':
        try:
            phone = '+91 98111 22334'
            message = ''
            sender_name = 'Rahul Verma'

            if request.content_type == 'application/json' or (request.body and request.body.startswith(b'{')):
                data = json.loads(request.body.decode('utf-8'))
                phone = data.get('phone', phone).strip()
                message = data.get('message', '').strip()
                sender_name = data.get('sender_name', sender_name).strip()
            else:
                phone = request.POST.get('phone', phone).strip()
                message = request.POST.get('message', '').strip()
                sender_name = request.POST.get('sender_name', sender_name).strip()

            clinic = Clinic.objects.first()
            if not clinic:
                return JsonResponse({'error': 'No clinic configured'}, status=400)

            if not message:
                return JsonResponse({'error': 'Message text is required'}, status=400)

            engine = ChatbotEngine(clinic)
            bot_reply = engine.process_incoming_message(phone, message, sender_name)

            return JsonResponse({
                'status': 'success',
                'user_message': message,
                'bot_reply': bot_reply,
                'phone': phone
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'POST required'}, status=405)
