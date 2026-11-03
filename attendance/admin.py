from django.contrib import admin

from .models import Attendance, OvertimeEntry, OvertimeType


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'check_in', 'check_out', 'status', 'source']
    list_filter = ['status', 'source', 'date']
    search_fields = ['employee__last_name']


@admin.register(OvertimeType)
class OvertimeTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'increase_rate', 'is_active', 'order']


@admin.register(OvertimeEntry)
class OvertimeEntryAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'overtime_type', 'hours']
    list_filter = ['overtime_type', 'date']
