from django.contrib import admin

from .models import Announcement, AuditLog, CompanySettings, Notification


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not CompanySettings.objects.exists()


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'department', 'publish_at', 'expires_at', 'is_pinned']
    list_filter = ['category', 'is_pinned']
    search_fields = ['title', 'content']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'level', 'is_read', 'created_at']
    list_filter = ['level', 'is_read']
    search_fields = ['title', 'user__email']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'action', 'model_name', 'object_repr', 'ip_address']
    list_filter = ['action', 'model_name']
    search_fields = ['object_repr', 'user__email']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
