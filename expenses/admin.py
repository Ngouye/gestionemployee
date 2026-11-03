from django.contrib import admin

from .models import ExpenseCategory, ExpenseClaim


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'max_amount', 'is_active']


@admin.register(ExpenseClaim)
class ExpenseClaimAdmin(admin.ModelAdmin):
    list_display = ['title', 'employee', 'category', 'expense_date', 'amount', 'status']
    list_filter = ['status', 'category']
