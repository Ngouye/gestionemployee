from django.contrib import admin

from .models import LeaveBalance, LeaveRequest, LeaveType, PublicHoliday


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'annual_allowance', 'tracks_balance', 'is_paid', 'is_active']


@admin.register(PublicHoliday)
class PublicHolidayAdmin(admin.ModelAdmin):
    list_display = ['name', 'date', 'is_recurring']


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ['employee', 'leave_type', 'year', 'allocated', 'carried_over']
    list_filter = ['year', 'leave_type']


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['employee', 'leave_type', 'start_date', 'end_date', 'days', 'status']
    list_filter = ['status', 'leave_type']
    search_fields = ['employee__last_name', 'employee__first_name']
