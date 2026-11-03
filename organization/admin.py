from django.contrib import admin

from .models import Department, Position


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'head', 'parent', 'is_active']
    search_fields = ['name', 'code']


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ['title', 'department', 'grade', 'is_active']
    list_filter = ['department', 'is_active']
    search_fields = ['title']
