from django import forms

from .models import Announcement, CompanySettings


class BootstrapFormMixin:
    """Ajoute automatiquement les classes Bootstrap et les widgets HTML5 adaptés."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.DateTimeInput):
                widget.input_type = 'datetime-local'
                widget.format = '%Y-%m-%dT%H:%M'
            elif isinstance(widget, forms.DateInput):
                widget.input_type = 'date'
                widget.format = '%Y-%m-%d'
            elif isinstance(widget, forms.TimeInput):
                widget.input_type = 'time'
                widget.format = '%H:%M'
            elif isinstance(widget, forms.ClearableFileInput):
                # Les fichiers ne sont pas servis publiquement : pas de lien direct.
                widget.template_name = 'widgets/file_input.html'

            if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect, forms.CheckboxSelectMultiple)):
                css = 'form-check-input'
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                css = 'form-select'
            else:
                css = 'form-control'
            if isinstance(widget, forms.Textarea):
                widget.attrs.setdefault('rows', 3)
            existing = widget.attrs.get('class', '')
            if css not in existing:
                widget.attrs['class'] = f'{existing} {css}'.strip()


class CompanySettingsForm(BootstrapFormMixin, forms.ModelForm):
    working_days = forms.MultipleChoiceField(
        label='Jours travaillés', choices=CompanySettings.WEEKDAYS,
        widget=forms.CheckboxSelectMultiple,
    )

    fieldsets = [
        ('Identité de l\'entreprise', ['name', 'legal_name', 'logo', 'registration_number',
                                        'tax_number', 'industry']),
        ('Coordonnées', ['address', 'city', 'country', 'phone', 'email', 'website']),
        ('Paramètres RH', ['currency', 'currency_decimals', 'working_days', 'work_start',
                           'work_end', 'late_tolerance_minutes', 'employee_id_prefix']),
        ('Paie', ['tax_allowance_rate', 'tax_allowance_cap']),
        ('Documents RH', ['hr_signatory_name', 'hr_signatory_title']),
    ]

    class Meta:
        model = CompanySettings
        fields = ['name', 'legal_name', 'logo', 'registration_number', 'tax_number', 'industry', 'address',
                  'city', 'country', 'phone', 'email', 'website', 'currency', 'currency_decimals', 'working_days',
                  'work_start', 'work_end', 'late_tolerance_minutes', 'employee_id_prefix', 'tax_allowance_rate',
                  'tax_allowance_cap', 'hr_signatory_name', 'hr_signatory_title']
        widgets = {'work_start': forms.TimeInput(), 'work_end': forms.TimeInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial['working_days'] = [str(d) for d in self.instance.working_days_list]

    def clean_working_days(self):
        days = self.cleaned_data['working_days']
        if not days:
            raise forms.ValidationError('Sélectionnez au moins un jour travaillé.')
        return ','.join(sorted(days))


class AnnouncementForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'content', 'category', 'department', 'is_pinned', 'publish_at', 'expires_at']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 6}),
            'publish_at': forms.DateTimeInput(),
            'expires_at': forms.DateTimeInput(),
        }

    def clean(self):
        data = super().clean()
        if data.get('publish_at') and data.get('expires_at') and data['expires_at'] <= data['publish_at']:
            self.add_error('expires_at', "La date d'expiration doit être postérieure à la publication.")
        return data
