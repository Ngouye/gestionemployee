from datetime import date

from django import forms
from django.contrib.auth import get_user_model

from core.forms import BootstrapFormMixin
from organization.models import Department, Position

from .models import Contract, Employee, EmployeeDocument

User = get_user_model()


EMPLOYEE_FIELDSETS = [
    ('Identité', ['first_name', 'last_name', 'gender', 'date_of_birth', 'place_of_birth',
                  'nationality', 'national_id', 'marital_status', 'children_count', 'photo']),
    ('Coordonnées', ['email', 'phone', 'personal_email', 'address', 'city']),
    ('Poste et organisation', ['employee_id', 'department', 'position', 'manager', 'hire_date',
                               'work_location']),
    ('Statut', ['status', 'exit_date', 'exit_reason']),
    ('Paie et sécurité sociale', ['social_security_number', 'tax_shares', 'payment_method',
                                  'bank_name', 'bank_account']),
    ("Contact d'urgence", ['emergency_contact_name', 'emergency_contact_relation',
                           'emergency_contact_phone']),
    ('Notes', ['notes']),
]


class EmployeeForm(BootstrapFormMixin, forms.ModelForm):
    fieldsets = EMPLOYEE_FIELDSETS

    class Meta:
        model = Employee
        fields = [name for _title, names in EMPLOYEE_FIELDSETS for name in names]
        widgets = {
            'date_of_birth': forms.DateInput(),
            'hire_date': forms.DateInput(),
            'exit_date': forms.DateInput(),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {'employee_id': 'Laisser vide pour une génération automatique.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee_id'].required = False
        self.fields['department'].queryset = Department.objects.filter(is_active=True)
        self.fields['position'].queryset = Position.objects.filter(is_active=True).select_related('department')
        managers = Employee.objects.active()
        if self.instance.pk:
            managers = managers.exclude(pk=self.instance.pk)
        self.fields['manager'].queryset = managers

    def clean_email(self):
        return self.cleaned_data['email'].lower()

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob and (date.today().year - dob.year) < 14:
            raise forms.ValidationError('Date de naissance invalide (âge minimum : 14 ans).')
        return dob

    def clean(self):
        data = super().clean()
        status, exit_date, hire_date = data.get('status'), data.get('exit_date'), data.get('hire_date')
        if status == Employee.Status.TERMINATED and not exit_date:
            self.add_error('exit_date', 'Indiquez la date de sortie.')
        if exit_date and hire_date and exit_date < hire_date:
            self.add_error('exit_date', "La date de sortie doit être postérieure à l'embauche.")
        manager = data.get('manager')
        node = manager
        while node is not None and self.instance.pk:
            if node.pk == self.instance.pk:
                self.add_error('manager', 'Cette hiérarchie créerait une boucle.')
                break
            node = node.manager
        return data


class EmployeeSelfForm(BootstrapFormMixin, forms.ModelForm):
    """Informations modifiables par l'employé lui-même."""

    class Meta:
        model = Employee
        fields = ['phone', 'personal_email', 'address', 'city', 'marital_status', 'children_count', 'photo',
                  'emergency_contact_name', 'emergency_contact_relation', 'emergency_contact_phone']


class ContractForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Contract
        fields = ['contract_type', 'position', 'start_date', 'end_date', 'trial_end_date', 'base_salary',
                  'weekly_hours', 'status', 'document', 'notes']
        widgets = {
            'start_date': forms.DateInput(), 'end_date': forms.DateInput(),
            'trial_end_date': forms.DateInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['position'].queryset = Position.objects.filter(is_active=True)

    def clean(self):
        data = super().clean()
        start, end, trial = data.get('start_date'), data.get('end_date'), data.get('trial_end_date')
        if data.get('contract_type') in (Contract.Type.CDD, Contract.Type.INTERNSHIP) and not end:
            self.add_error('end_date', 'La date de fin est obligatoire pour ce type de contrat.')
        if start and end and end < start:
            self.add_error('end_date', 'La date de fin doit être postérieure au début.')
        if start and trial and trial < start:
            self.add_error('trial_end_date', "La fin de période d'essai doit être postérieure au début.")
        if data.get('base_salary') is not None and data['base_salary'] < 0:
            self.add_error('base_salary', 'Le salaire ne peut pas être négatif.')
        return data


class InitialContractForm(BootstrapFormMixin, forms.ModelForm):
    """Contrat créé en même temps que la fiche employé."""

    class Meta:
        model = Contract
        fields = ['contract_type', 'end_date', 'trial_end_date', 'base_salary', 'weekly_hours']
        widgets = {'end_date': forms.DateInput(), 'trial_end_date': forms.DateInput()}

    def clean(self):
        data = super().clean()
        if data.get('contract_type') in (Contract.Type.CDD, Contract.Type.INTERNSHIP) and not data.get('end_date'):
            self.add_error('end_date', 'La date de fin est obligatoire pour ce type de contrat.')
        return data


class AccountForm(BootstrapFormMixin, forms.Form):
    create_account = forms.BooleanField(
        label="Créer un compte d'accès à l'application", required=False, initial=True,
        help_text='Un mot de passe temporaire sera généré ; il devra être changé à la première connexion.',
    )
    role = forms.ChoiceField(label='Rôle', choices=User.Role.choices, initial=User.Role.EMPLOYEE)


class EmployeeDocumentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = EmployeeDocument
        fields = ['title', 'category', 'file', 'expires_on', 'visible_to_employee', 'notes']
        widgets = {'expires_on': forms.DateInput()}


class EmployeeImportForm(BootstrapFormMixin, forms.Form):
    file = forms.FileField(label='Fichier Excel (.xlsx) ou CSV',
                           help_text='Utilisez le modèle fourni. Les départements et postes inconnus sont créés.')

    def clean_file(self):
        uploaded = self.cleaned_data['file']
        name = uploaded.name.lower()
        if not name.endswith(('.xlsx', '.csv')):
            raise forms.ValidationError('Format accepté : .xlsx ou .csv')
        if uploaded.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Fichier trop volumineux (5 Mo maximum).')
        return uploaded
