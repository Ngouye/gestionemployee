from django import forms
from django.contrib.auth import get_user_model

from core.forms import BootstrapFormMixin

from .models import Application, Interview, JobOpening


class JobOpeningForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = JobOpening
        fields = ['title', 'department', 'position', 'location', 'contract_type', 'openings', 'salary_range',
                  'closing_date', 'status', 'is_public', 'description', 'requirements']
        widgets = {'closing_date': forms.DateInput(), 'description': forms.Textarea(attrs={'rows': 6}),
                   'requirements': forms.Textarea(attrs={'rows': 5})}


class ApplicationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Application
        fields = ['job', 'first_name', 'last_name', 'email', 'phone', 'source', 'stage', 'rating', 'resume',
                  'cover_letter', 'notes']
        widgets = {'cover_letter': forms.Textarea(attrs={'rows': 4})}


class PublicApplicationForm(BootstrapFormMixin, forms.ModelForm):
    """Formulaire de la page carrières (sans authentification)."""

    website = forms.CharField(required=False, widget=forms.TextInput(attrs={'autocomplete': 'off', 'tabindex': '-1'}),
                              label='Site web')  # piège anti-robots
    consent = forms.BooleanField(
        label="J'accepte que mes données soient utilisées dans le cadre de ce recrutement.", required=True)

    class Meta:
        model = Application
        fields = ['first_name', 'last_name', 'email', 'phone', 'resume', 'cover_letter']
        widgets = {'cover_letter': forms.Textarea(attrs={'rows': 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['resume'].required = True

    def clean_website(self):
        if self.cleaned_data.get('website'):
            raise forms.ValidationError('Requête invalide.')
        return ''


class InterviewForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Interview
        fields = ['scheduled_at', 'duration_minutes', 'mode', 'location', 'interviewer', 'status', 'rating',
                  'feedback']
        widgets = {'scheduled_at': forms.DateTimeInput(), 'feedback': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['interviewer'].queryset = get_user_model().objects.filter(is_active=True)


class InterviewFeedbackForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Interview
        fields = ['status', 'rating', 'feedback']
        widgets = {'feedback': forms.Textarea(attrs={'rows': 5})}
