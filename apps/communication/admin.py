from django.contrib import admin
from apps.communication.models import WhatsAppConversation, WhatsAppMessage

class WhatsAppMessageInline(admin.TabularInline):
    model = WhatsAppMessage
    extra = 0
    readonly_fields = ('created_at',)

@admin.register(WhatsAppConversation)
class WhatsAppConversationAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'clinic', 'patient', 'status', 'last_message_at')
    list_filter = ('clinic', 'status')
    search_fields = ('phone_number', 'patient__first_name', 'patient__last_name')
    inlines = [WhatsAppMessageInline]

@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'sender', 'text', 'created_at')
    list_filter = ('sender', 'is_read')
