from django.contrib import admin

from .models import Contract, Employee, EmployeeDocument


class ContractInline(admin.TabularInline):
    model = Contract
    extra = 0


class DocumentInline(admin.TabularInline):
    model = EmployeeDocument
    extra = 0


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['employee_id', 'last_name', 'first_name', 'email', 'department', 'position', 'status']
    list_filter = ['status', 'department', 'gender']
    search_fields = ['employee_id', 'first_name', 'last_name', 'email']
    raw_id_fields = ['user', 'manager']
    inlines = [ContractInline, DocumentInline]


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ['reference', 'employee', 'contract_type', 'start_date', 'end_date', 'base_salary', 'status']
    list_filter = ['contract_type', 'status']
    search_fields = ['reference', 'employee__last_name']
