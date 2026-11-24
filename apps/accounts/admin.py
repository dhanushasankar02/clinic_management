from django.contrib import admin
from apps.accounts.models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'clinic', 'role', 'phone')
    list_filter = ('role', 'clinic')
