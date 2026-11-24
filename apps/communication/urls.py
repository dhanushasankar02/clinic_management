from django.urls import path
from apps.communication.views import inbox_view, send_agent_message, whatsapp_webhook, notifications_view, notification_mark_read

app_name = 'communication'

urlpatterns = [
    path('', inbox_view, name='inbox'),
    path('notifications/', notifications_view, name='notifications'),
    path('notifications/<int:pk>/read/', notification_mark_read, name='notification_read'),
    path('chat/<int:chat_id>/send/', send_agent_message, name='send_agent_message'),
    path('webhook/', whatsapp_webhook, name='webhook'),
]
