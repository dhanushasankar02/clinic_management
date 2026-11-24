from django.urls import path
from apps.chatbot.views import test_chatbot, simulate_chat_api

app_name = 'chatbot'

urlpatterns = [
    path('test/', test_chatbot, name='test'),
    path('api/simulate/', simulate_chat_api, name='simulate_api'),
]
