from django.contrib import admin

from .models import Application, Interview, JobOpening


@admin.register(JobOpening)
class JobOpeningAdmin(admin.ModelAdmin):
    list_display = ['title', 'department', 'contract_type', 'status', 'closing_date']
    list_filter = ['status', 'contract_type']


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'job', 'stage', 'source', 'created_at']
    list_filter = ['stage', 'source', 'job']
    search_fields = ['first_name', 'last_name', 'email']


@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    list_display = ['application', 'scheduled_at', 'interviewer', 'status']
