from decimal import Decimal

from django import forms

from core.forms import BootstrapFormMixin
from employees.models import Employee
from payroll.models import PayrollPeriod

from .models import Attendance, OvertimeEntry, OvertimeType


class AttendanceForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['employee', 'date', 'check_in', 'check_out', 'status', 'note']
        widgets = {'date': forms.DateInput(), 'check_in': forms.TimeInput(), 'check_out': forms.TimeInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Employee.objects.active()

    def clean(self):
        data = super().clean()
        check_in, check_out = data.get('check_in'), data.get('check_out')
        if check_in and check_out and check_out <= check_in:
            self.add_error('check_out', "L'heure de départ doit être après l'heure d'arrivée.")
        if data.get('status') in (Attendance.Status.PRESENT, Attendance.Status.LATE) and not check_in:
            self.add_error('check_in', "Indiquez l'heure d'arrivée.")
        return data


class OvertimeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = OvertimeEntry
        fields = ['employee', 'date', 'overtime_type', 'hours', 'note']
        widgets = {'date': forms.DateInput()}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        employees = Employee.objects.active()
        if user is not None and not user.is_hr:
            employees = employees.filter(manager=user.employee_profile)
        self.fields['employee'].queryset = employees
        self.fields['overtime_type'].queryset = OvertimeType.objects.filter(is_active=True)

    def clean_hours(self):
        hours = self.cleaned_data['hours']
        if hours <= 0 or hours > Decimal(16):
            raise forms.ValidationError('Indiquez un nombre d’heures compris entre 0 et 16.')
        return hours

    def clean_date(self):
        day = self.cleaned_data['date']
        locked = PayrollPeriod.objects.filter(year=day.year, month=day.month).exclude(
            status=PayrollPeriod.Status.DRAFT).exists()
        if locked:
            raise forms.ValidationError('La paie de ce mois est déjà validée : ces heures ne peuvent plus être '
                                        'modifiées.')
        return day


class OvertimeTypeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = OvertimeType
        fields = ['name', 'code', 'increase_rate', 'order', 'is_active']
