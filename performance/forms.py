from django import forms

from core.forms import BootstrapFormMixin
from employees.models import Employee

from .models import Objective, PerformanceReview, ReviewCycle


class ReviewCycleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ReviewCycle
        fields = ['name', 'start_date', 'end_date', 'status', 'description']
        widgets = {'start_date': forms.DateInput(), 'end_date': forms.DateInput()}

    def clean(self):
        data = super().clean()
        if data.get('start_date') and data.get('end_date') and data['end_date'] < data['start_date']:
            self.add_error('end_date', 'La fin doit être postérieure au début.')
        return data


class ReviewForm(BootstrapFormMixin, forms.ModelForm):
    finalize = forms.BooleanField(label="Finaliser l'évaluation (l'employé en sera informé)", required=False)

    class Meta:
        model = PerformanceReview
        fields = ['quality_rating', 'productivity_rating', 'teamwork_rating', 'initiative_rating',
                  'overall_rating', 'strengths', 'improvements', 'next_goals', 'reviewer_comments']

    def clean(self):
        data = super().clean()
        if data.get('finalize') and not data.get('overall_rating'):
            self.add_error('overall_rating', "L'appréciation globale est requise pour finaliser.")
        return data


class SelfAssessmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PerformanceReview
        fields = ['self_assessment']
        widgets = {'self_assessment': forms.Textarea(attrs={'rows': 5})}


class EmployeeCommentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PerformanceReview
        fields = ['employee_comments']
        widgets = {'employee_comments': forms.Textarea(attrs={'rows': 3})}


class ObjectiveForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Objective
        fields = ['employee', 'cycle', 'title', 'description', 'due_date', 'progress', 'status']
        widgets = {'due_date': forms.DateInput()}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        employees = Employee.objects.active()
        if user is not None and not user.is_hr:
            employees = employees.filter(manager=user.employee_profile)
        self.fields['employee'].queryset = employees


class ObjectiveProgressForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Objective
        fields = ['progress', 'status']
