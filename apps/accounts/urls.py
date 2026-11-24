from django.urls import path
from apps.accounts import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('password-change/', views.password_change_view, name='password_change'),
    path('my-logins/', views.my_login_history_view, name='my_logins'),
    path('users/', views.users_list_view, name='users_list'),
    path('users/<int:user_id>/toggle-active/', views.user_toggle_active, name='user_toggle_active'),
    path('users/<int:user_id>/edit-role/', views.user_edit_role, name='user_edit_role'),
    path('login-activity/', views.login_activity_view, name='login_activity'),
    path('audit-logs/', views.audit_logs_view, name='audit_logs'),
]
