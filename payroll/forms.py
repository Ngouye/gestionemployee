from django import forms
from django.utils import timezone

from core.forms import BootstrapFormMixin
from core.utils import MONTHS_FR
from employees.models import Employee

from .models import PayrollPeriod, PayrollRule, SalaryItem, TaxBracket

MONTH_CHOICES = [(i + 1, m.capitalize()) for i, m in enumerate(MONTHS_FR)]


class PayrollPeriodForm(BootstrapFormMixin, forms.ModelForm):
    month = forms.TypedChoiceField(label='Mois', choices=MONTH_CHOICES, coerce=int)

    class Meta:
        model = PayrollPeriod
        fields = ['year', 'month', 'payment_date', 'notes']
        widgets = {'payment_date': forms.DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields['year'].initial = today.year
        self.fields['month'].initial = today.month


class PayrollRuleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PayrollRule
        fields = ['code', 'name', 'base', 'applies_to', 'employee_rate', 'employer_rate', 'ceiling',
                  'is_tax_deductible', 'order', 'is_active', 'notes']


class TaxBracketForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TaxBracket
        fields = ['lower_bound', 'upper_bound', 'rate']

    def clean(self):
        data = super().clean()
        low, high = data.get('lower_bound'), data.get('upper_bound')
        if low is not None and high is not None and high <= low:
            self.add_error('upper_bound', 'La borne supérieure doit dépasser la borne inférieure.')
        return data


class SalaryItemForm(BootstrapFormMixin, forms.ModelForm):
    month = forms.TypedChoiceField(label='Mois (si ponctuel)', choices=[('', '—')] + MONTH_CHOICES,
                                   coerce=int, required=False, empty_value=None)

    class Meta:
        model = SalaryItem
        fields = ['employee', 'label', 'kind', 'amount', 'is_taxable', 'is_recurring', 'year', 'month', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Employee.objects.active()

    def clean(self):
        data = super().clean()
        if not data.get('is_recurring') and not (data.get('year') and data.get('month')):
            raise forms.ValidationError('Pour un élément ponctuel, indiquez l’année et le mois concernés.')
        if data.get('amount') is not None and data['amount'] <= 0:
            self.add_error('amount', 'Le montant doit être positif.')
        return data
