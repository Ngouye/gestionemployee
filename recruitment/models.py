from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.models import TimeStampedModel
from core.validators import document_validators
from employees.models import Contract


class JobOpening(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Brouillon'
        OPEN = 'OPEN', 'Ouverte'
        CLOSED = 'CLOSED', 'Clôturée'

    title = models.CharField('intitulé', max_length=200)
    department = models.ForeignKey('organization.Department', on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name='département')
    position = models.ForeignKey('organization.Position', on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name='poste de référence')
    location = models.CharField('lieu', max_length=120, default='Dakar')
    contract_type = models.CharField('type de contrat', max_length=10, choices=Contract.Type.choices,
                                     default=Contract.Type.CDI)
    openings = models.PositiveSmallIntegerField('nombre de postes', default=1)
    description = models.TextField('description du poste')
    requirements = models.TextField('profil recherché', blank=True)
    salary_range = models.CharField('rémunération indicative', max_length=120, blank=True)
    closing_date = models.DateField('date limite de candidature', null=True, blank=True)
    status = models.CharField('statut', max_length=10, choices=Status.choices, default=Status.DRAFT)
    is_public = models.BooleanField('publiée sur la page carrières', default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name='créée par')

    class Meta:
        verbose_name = "offre d'emploi"
        verbose_name_plural = "offres d'emploi"
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('recruitment:job_detail', args=[self.pk])

    @property
    def is_published(self):
        return (self.status == self.Status.OPEN and self.is_public
                and (self.closing_date is None or self.closing_date >= timezone.localdate()))


class Application(TimeStampedModel):
    class Stage(models.TextChoices):
        NEW = 'NEW', 'Nouvelle'
        SCREENING = 'SCREENING', 'Présélection'
        INTERVIEW = 'INTERVIEW', 'Entretien'
        OFFER = 'OFFER', 'Offre'
        HIRED = 'HIRED', 'Embauché(e)'
        REJECTED = 'REJECTED', 'Non retenue'

    class Source(models.TextChoices):
        CAREERS = 'CAREERS', 'Page carrières'
        REFERRAL = 'REFERRAL', 'Cooptation'
        LINKEDIN = 'LINKEDIN', 'LinkedIn'
        JOB_BOARD = 'JOB_BOARD', "Site d'emploi"
        SPONTANEOUS = 'SPONTANEOUS', 'Candidature spontanée'
        OTHER = 'OTHER', 'Autre'

    job = models.ForeignKey(JobOpening, on_delete=models.CASCADE, related_name='applications',
                            verbose_name='offre')
    first_name = models.CharField('prénom', max_length=100)
    last_name = models.CharField('nom', max_length=100)
    email = models.EmailField('e-mail')
    phone = models.CharField('téléphone', max_length=30, blank=True)
    resume = models.FileField('CV', upload_to='recrutement/cv/%Y/', blank=True, validators=document_validators)
    cover_letter = models.TextField('lettre de motivation', blank=True)
    source = models.CharField('source', max_length=12, choices=Source.choices, default=Source.CAREERS)
    stage = models.CharField('étape', max_length=10, choices=Stage.choices, default=Stage.NEW)
    rating = models.PositiveSmallIntegerField('évaluation (1 à 5)', null=True, blank=True,
                                              choices=[(i, '★' * i) for i in range(1, 6)])
    notes = models.TextField('notes internes', blank=True)
    hired_employee = models.ForeignKey('employees.Employee', on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='applications', verbose_name='fiche employé créée')

    class Meta:
        verbose_name = 'candidature'
        verbose_name_plural = 'candidatures'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.full_name} — {self.job}'

    def get_absolute_url(self):
        return reverse('recruitment:application_detail', args=[self.pk])

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'


class Interview(TimeStampedModel):
    class Mode(models.TextChoices):
        ONSITE = 'ONSITE', 'Présentiel'
        VIDEO = 'VIDEO', 'Visioconférence'
        PHONE = 'PHONE', 'Téléphone'

    class Status(models.TextChoices):
        SCHEDULED = 'SCHEDULED', 'Planifié'
        DONE = 'DONE', 'Réalisé'
        CANCELLED = 'CANCELLED', 'Annulé'

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='interviews',
                                    verbose_name='candidature')
    scheduled_at = models.DateTimeField('date et heure')
    duration_minutes = models.PositiveSmallIntegerField('durée (minutes)', default=60)
    mode = models.CharField('format', max_length=10, choices=Mode.choices, default=Mode.ONSITE)
    location = models.CharField('lieu ou lien', max_length=255, blank=True)
    interviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='interviews', verbose_name='intervieweur')
    status = models.CharField('statut', max_length=10, choices=Status.choices, default=Status.SCHEDULED)
    rating = models.PositiveSmallIntegerField('note (1 à 5)', null=True, blank=True,
                                              choices=[(i, '★' * i) for i in range(1, 6)])
    feedback = models.TextField('compte rendu', blank=True)

    class Meta:
        verbose_name = 'entretien'
        verbose_name_plural = 'entretiens'
        ordering = ['scheduled_at']

    def __str__(self):
        return f'Entretien {self.application.full_name} — {timezone.localtime(self.scheduled_at):%d/%m/%Y %H:%M}'
