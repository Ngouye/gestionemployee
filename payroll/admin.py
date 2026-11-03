from django.contrib import admin

from .models import PayrollPeriod, PayrollRule, Payslip, PayslipLine, SalaryItem, TaxBracket


@admin.register(PayrollRule)
class PayrollRuleAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'base', 'employee_rate', 'employer_rate', 'ceiling', 'is_active', 'order']


@admin.register(TaxBracket)
class TaxBracketAdmin(admin.ModelAdmin):
    list_display = ['lower_bound', 'upper_bound', 'rate']


@admin.register(SalaryItem)
class SalaryItemAdmin(admin.ModelAdmin):
    list_display = ['employee', 'label', 'kind', 'amount', 'is_recurring', 'is_active']
    list_filter = ['kind', 'is_recurring']


class PayslipLineInline(admin.TabularInline):
    model = PayslipLine
    extra = 0


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ['number', 'employee_name', 'period', 'gross_salary', 'net_salary']
    list_filter = ['period']
    inlines = [PayslipLineInline]


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'status', 'payment_date', 'validated_at']
