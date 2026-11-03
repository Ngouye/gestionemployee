from django.contrib import admin

from .models import Training, TrainingParticipant


class ParticipantInline(admin.TabularInline):
    model = TrainingParticipant
    extra = 0


@admin.register(Training)
class TrainingAdmin(admin.ModelAdmin):
    list_display = ['title', 'provider', 'start_date', 'end_date', 'status']
    list_filter = ['status', 'mode']
    inlines = [ParticipantInline]
