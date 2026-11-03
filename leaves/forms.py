from django import forms

from core.forms import BootstrapFormMixin
from employees.models import Employee

from . import services
from .models import LeaveBalance, LeaveRequest, LeaveType, PublicHoliday


class LeaveRequestForm(BootstrapFormMixin, forms.ModelForm):
    check_balance = True

    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'start_date', 'end_date', 'half_day', 'reason', 'attachment']
        widgets = {'start_date': forms.DateInput(), 'end_date': forms.DateInput(),
                   'reason': forms.Textarea(attrs={'rows': 3})}
        help_texts = {'half_day': 'Uniquement pour une absence sur une seule journée.'}

    def __init__(self, *args, employee=None, **kwargs):
        self.employee = employee
        super().__init__(*args, **kwargs)
        self.fields['leave_type'].queryset = LeaveType.objects.filter(is_active=True)

    def get_employee(self, data):
        return self.employee

    def clean(self):
        data = super().clean()
        employee = self.get_employee(data)
        start, end = data.get('start_date'), data.get('end_date')
        leave_type = data.get('leave_type')
        if not (start and end and leave_type and employee):
            return data
        if end < start:
            self.add_error('end_date', 'La date de fin doit être postérieure ou égale au début.')
            return data
        if data.get('half_day') and start != end:
            self.add_error('half_day', 'La demi-journée ne concerne qu’une seule date.')
            return data
        days = services.working_days(start, end, data.get('half_day'))
        if days <= 0:
            raise forms.ValidationError('La période choisie ne contient aucun jour ouvré.')
        if services.overlapping_requests(employee, start, end, exclude_pk=self.instance.pk).exists():
            raise forms.ValidationError('Une demande en attente ou approuvée existe déjà sur cette période.')
        if leave_type.requires_attachment and not data.get('attachment') and not self.instance.attachment:
            self.add_error('attachment', 'Un justificatif est obligatoire pour ce type de congé.')
        if self.check_balance and leave_type.tracks_balance:
            remaining = services.remaining_days(employee, leave_type, start.year, exclude_pk=self.instance.pk)
            if days > remaining:
                raise forms.ValidationError(
                    f'Solde insuffisant : {days} jour(s) demandé(s), {remaining} disponible(s) '
                    f'pour « {leave_type} » en {start.year}.')
        self.instance.days = days
        return data


class HRLeaveForm(LeaveRequestForm):
    """Saisie d'une absence par les RH pour le compte d'un employé (validée directement)."""

    check_balance = False

    class Meta(LeaveRequestForm.Meta):
        fields = ['employee'] + LeaveRequestForm.Meta.fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Employee.objects.active()

    def get_employee(self, data):
        return data.get('employee')


class LeaveDecisionForm(forms.Form):
    decision = forms.ChoiceField(choices=[('approve', 'Approuver'), ('reject', 'Refuser')])
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def clean(self):
        data = super().clean()
        if data.get('decision') == 'reject' and not data.get('comment', '').strip():
            raise forms.ValidationError('Indiquez le motif du refus.')
        return data


class LeaveTypeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = LeaveType
        fields = ['name', 'code', 'color', 'annual_allowance', 'tracks_balance', 'is_paid',
                  'requires_attachment', 'max_carry_over', 'description', 'is_active']
        widgets = {'color': forms.TextInput(attrs={'type': 'color', 'class': 'form-control-color'})}


class PublicHolidayForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PublicHoliday
        fields = ['name', 'date', 'is_recurring']
        widgets = {'date': forms.DateInput()}


class LeaveBalanceForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = LeaveBalance
        fields = ['allocated', 'carried_over', 'notes']
