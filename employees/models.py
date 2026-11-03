from datetime import timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property

from core.models import CompanySettings, TimeStampedModel
from core.validators import document_validators, image_validators


class EmployeeQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status=Employee.Status.ACTIVE)

    def visible_to(self, user):
        """Employés qu'un utilisateur peut consulter dans les écrans de gestion."""
        if user.is_hr:
            return self
        employee = user.employee_profile
        if employee is None:
            return self.none()
        return self.filter(models.Q(manager=employee) | models.Q(pk=employee.pk))


class Employee(TimeStampedModel):
    class Gender(models.TextChoices):
        MALE = 'M', 'Homme'
        FEMALE = 'F', 'Femme'

    class MaritalStatus(models.TextChoices):
        SINGLE = 'SINGLE', 'Célibataire'
        MARRIED = 'MARRIED', 'Marié(e)'
        DIVORCED = 'DIVORCED', 'Divorcé(e)'
        WIDOWED = 'WIDOWED', 'Veuf / veuve'

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Actif'
        SUSPENDED = 'SUSPENDED', 'Suspendu'
        TERMINATED = 'TERMINATED', 'Sorti'

    class PaymentMethod(models.TextChoices):
        TRANSFER = 'TRANSFER', 'Virement bancaire'
        MOBILE = 'MOBILE', 'Mobile money'
        CHEQUE = 'CHEQUE', 'Chèque'
        CASH = 'CASH', 'Espèces'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='employee', verbose_name='compte utilisateur')
    employee_id = models.CharField('matricule', max_length=20, unique=True, blank=True)
    first_name = models.CharField('prénom', max_length=100)
    last_name = models.CharField('nom', max_length=100)
    gender = models.CharField('genre', max_length=1, choices=Gender.choices, blank=True)
    date_of_birth = models.DateField('date de naissance', null=True, blank=True)
    place_of_birth = models.CharField('lieu de naissance', max_length=120, blank=True)
    nationality = models.CharField('nationalité', max_length=80, blank=True, default='Sénégalaise')
    national_id = models.CharField("n° de pièce d'identité", max_length=50, blank=True)
    marital_status = models.CharField('situation familiale', max_length=10,
                                      choices=MaritalStatus.choices, blank=True)
    children_count = models.PositiveSmallIntegerField("nombre d'enfants à charge", default=0)
    photo = models.ImageField('photo', upload_to='employes/photos/', blank=True, validators=image_validators)

    email = models.EmailField('e-mail professionnel', unique=True)
    personal_email = models.EmailField('e-mail personnel', blank=True)
    phone = models.CharField('téléphone', max_length=30, blank=True)
    address = models.CharField('adresse', max_length=255, blank=True)
    city = models.CharField('ville', max_length=100, blank=True)

    department = models.ForeignKey('organization.Department', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='employees', verbose_name='département')
    position = models.ForeignKey('organization.Position', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='employees', verbose_name='poste')
    manager = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='subordinates', verbose_name='responsable hiérarchique')
    hire_date = models.DateField("date d'embauche")
    work_location = models.CharField('lieu de travail', max_length=120, blank=True)
    status = models.CharField('statut', max_length=12, choices=Status.choices, default=Status.ACTIVE)
    exit_date = models.DateField('date de sortie', null=True, blank=True)
    exit_reason = models.CharField('motif de sortie', max_length=255, blank=True)

    social_security_number = models.CharField('n° de sécurité sociale (IPRES / CSS)', max_length=50, blank=True)
    tax_shares = models.DecimalField('nombre de parts fiscales', max_digits=3, decimal_places=1, default=1,
                                     help_text="Utilisé pour le calcul de l'impôt sur le revenu.")
    payment_method = models.CharField('mode de paiement', max_length=10, choices=PaymentMethod.choices,
                                      default=PaymentMethod.TRANSFER)
    bank_name = models.CharField('banque', max_length=100, blank=True)
    bank_account = models.CharField('RIB / IBAN / n° de compte', max_length=60, blank=True)

    emergency_contact_name = models.CharField("contact d'urgence", max_length=150, blank=True)
    emergency_contact_relation = models.CharField('lien de parenté', max_length=60, blank=True)
    emergency_contact_phone = models.CharField("téléphone d'urgence", max_length=30, blank=True)
    notes = models.TextField('notes internes RH', blank=True)

    objects = EmployeeQuerySet.as_manager()

    class Meta:
        verbose_name = 'employé'
        verbose_name_plural = 'employés'
        ordering = ['last_name', 'first_name']
        indexes = [models.Index(fields=['status']), models.Index(fields=['last_name', 'first_name'])]

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        if not self.employee_id:
            self.employee_id = self.next_employee_id()
        if self.email:
            self.email = self.email.lower()
        super().save(*args, **kwargs)

    @classmethod
    def next_employee_id(cls):
        prefix = CompanySettings.load().employee_id_prefix or 'EMP'
        highest = 0
        for value in cls.objects.filter(employee_id__startswith=prefix).values_list('employee_id', flat=True):
            suffix = value[len(prefix):].lstrip('-')
            if suffix.isdigit():
                highest = max(highest, int(suffix))
        return f'{prefix}-{highest + 1:04d}'

    def get_absolute_url(self):
        return reverse('employees:detail', args=[self.pk])

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = timezone.localdate()
        dob = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    @property
    def seniority(self):
        """Ancienneté lisible (ex. « 3 ans 2 mois »)."""
        end = self.exit_date or timezone.localdate()
        months = (end.year - self.hire_date.year) * 12 + end.month - self.hire_date.month
        if end.day < self.hire_date.day:
            months -= 1
        months = max(months, 0)
        years, months = divmod(months, 12)
        parts = []
        if years:
            parts.append(f'{years} an{"s" if years > 1 else ""}')
        if months or not years:
            parts.append(f'{months} mois')
        return ' '.join(parts)

    @cached_property
    def current_contract(self):
        """Contrat en cours (utilise le préchargement `contracts` s'il existe)."""
        today = timezone.localdate()
        active = sorted((c for c in self.contracts.all() if c.status == Contract.Status.ACTIVE),
                        key=lambda c: c.start_date, reverse=True)
        started = [c for c in active if c.start_date <= today]
        return (started or active or [None])[0]

    @property
    def base_salary(self):
        contract = self.current_contract
        return contract.base_salary if contract else None

    def is_managed_by(self, user):
        return bool(self.manager_id and self.manager.user_id and self.manager.user_id == user.pk)


class Contract(TimeStampedModel):
    class Type(models.TextChoices):
        CDI = 'CDI', 'CDI — Contrat à durée indéterminée'
        CDD = 'CDD', 'CDD — Contrat à durée déterminée'
        INTERNSHIP = 'STAGE', 'Stage'
        APPRENTICESHIP = 'APPRENTI', 'Apprentissage'
        TEMPORARY = 'INTERIM', 'Intérim'
        CONSULTANT = 'PRESTA', 'Prestataire / consultant'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Brouillon'
        ACTIVE = 'ACTIVE', 'En cours'
        ENDED = 'ENDED', 'Terminé'
        TERMINATED = 'TERMINATED', 'Rompu'

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='contracts',
                                 verbose_name='employé')
    reference = models.CharField('référence', max_length=40, blank=True)
    contract_type = models.CharField('type de contrat', max_length=10, choices=Type.choices, default=Type.CDI)
    position = models.ForeignKey('organization.Position', on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name='poste')
    start_date = models.DateField('date de début')
    end_date = models.DateField('date de fin', null=True, blank=True)
    trial_end_date = models.DateField("fin de période d'essai", null=True, blank=True)
    base_salary = models.DecimalField('salaire de base mensuel brut', max_digits=12, decimal_places=2)
    weekly_hours = models.DecimalField('heures hebdomadaires', max_digits=4, decimal_places=1, default=40)
    status = models.CharField('statut', max_length=12, choices=Status.choices, default=Status.ACTIVE)
    document = models.FileField('contrat signé', upload_to='employes/contrats/', blank=True,
                                validators=document_validators)
    notes = models.TextField('notes', blank=True)

    class Meta:
        verbose_name = 'contrat'
        verbose_name_plural = 'contrats'
        ordering = ['-start_date']

    def __str__(self):
        return f'{self.reference or self.get_contract_type_display()} — {self.employee}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.reference:
            self.reference = f'CTR-{self.start_date:%Y}-{self.pk:05d}'
            super().save(update_fields=['reference'])

    @property
    def days_until_end(self):
        if not self.end_date:
            return None
        return (self.end_date - timezone.localdate()).days

    @property
    def is_expiring_soon(self):
        remaining = self.days_until_end
        return remaining is not None and 0 <= remaining <= 30

    @property
    def in_trial(self):
        return bool(self.trial_end_date and self.trial_end_date >= timezone.localdate())


class EmployeeDocument(TimeStampedModel):
    class Category(models.TextChoices):
        CONTRACT = 'CONTRACT', 'Contrat / avenant'
        ID = 'ID', "Pièce d'identité"
        CV = 'CV', 'CV'
        DIPLOMA = 'DIPLOMA', 'Diplôme / certificat'
        MEDICAL = 'MEDICAL', 'Certificat médical'
        ADMIN = 'ADMIN', 'Document administratif'
        OTHER = 'OTHER', 'Autre'

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='documents',
                                 verbose_name='employé')
    title = models.CharField('titre', max_length=200)
    category = models.CharField('catégorie', max_length=10, choices=Category.choices, default=Category.OTHER)
    file = models.FileField('fichier', upload_to='employes/documents/%Y/', validators=document_validators)
    expires_on = models.DateField("date d'expiration", null=True, blank=True)
    visible_to_employee = models.BooleanField("visible par l'employé", default=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    verbose_name='ajouté par')
    notes = models.CharField('notes', max_length=255, blank=True)

    class Meta:
        verbose_name = 'document employé'
        verbose_name_plural = 'documents employés'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def is_expired(self):
        return bool(self.expires_on and self.expires_on < timezone.localdate())

    @property
    def expires_soon(self):
        return bool(self.expires_on and timezone.localdate() <= self.expires_on
                    <= timezone.localdate() + timedelta(days=30))
