from django.contrib import admin

from .models import Objective, PerformanceReview, ReviewCycle


@admin.register(ReviewCycle)
class ReviewCycleAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'status']


@admin.register(PerformanceReview)
class PerformanceReviewAdmin(admin.ModelAdmin):
    list_display = ['employee', 'cycle', 'reviewer', 'overall_rating', 'status']
    list_filter = ['cycle', 'status']


@admin.register(Objective)
class ObjectiveAdmin(admin.ModelAdmin):
    list_display = ['title', 'employee', 'due_date', 'progress', 'status']
    list_filter = ['status']
