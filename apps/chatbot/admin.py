from django.contrib import admin
from apps.chatbot.models import BotIntent, ClinicFAQ

@admin.register(BotIntent)
class BotIntentAdmin(admin.ModelAdmin):
    list_display = ('name', 'action', 'is_active')
    list_filter = ('action', 'is_active')

@admin.register(ClinicFAQ)
class ClinicFAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'clinic', 'is_active')
    list_filter = ('clinic', 'is_active')
