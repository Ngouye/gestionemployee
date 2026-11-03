from django import forms

from core.forms import BootstrapFormMixin
from employees.models import Employee

from .models import Training, TrainingParticipant


class TrainingForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Training
        fields = ['title', 'category', 'provider', 'trainer', 'start_date', 'end_date', 'duration_hours', 'mode',
                  'location', 'capacity', 'cost', 'status', 'is_open_for_requests', 'description']
        widgets = {'start_date': forms.DateInput(), 'end_date': forms.DateInput(),
                   'description': forms.Textarea(attrs={'rows': 5})}

    def clean(self):
        data = super().clean()
        if data.get('start_date') and data.get('end_date') and data['end_date'] < data['start_date']:
            self.add_error('end_date', 'La fin doit être postérieure au début.')
        return data


class EnrollForm(BootstrapFormMixin, forms.Form):
    employees = forms.ModelMultipleChoiceField(label='Employés à inscrire', queryset=Employee.objects.none(),
                                               widget=forms.SelectMultiple(attrs={'size': 8}))

    def __init__(self, *args, training=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Employee.objects.active()
        if training is not None:
            queryset = queryset.exclude(training_participations__training=training)
        self.fields['employees'].queryset = queryset


class ParticipantForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TrainingParticipant
        fields = ['status', 'certificate']


class FeedbackForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TrainingParticipant
        fields = ['satisfaction', 'feedback']
        widgets = {'feedback': forms.Textarea(attrs={'rows': 3})}
