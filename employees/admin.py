from django.contrib import admin
from .models import Employee

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'position', 'salary', 'hire_date')
    search_fields = ('name', 'email', 'position')
