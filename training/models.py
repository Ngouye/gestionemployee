from django.db import models
from django.urls import reverse

from core.models import TimeStampedModel
from core.validators import document_validators


class Training(TimeStampedModel):
    class Status(models.TextChoices):
        PLANNED = 'PLANNED', 'Planifiée'
        ONGOING = 'ONGOING', 'En cours'
        COMPLETED = 'COMPLETED', 'Terminée'
        CANCELLED = 'CANCELLED', 'Annulée'

    class Mode(models.TextChoices):
        ONSITE = 'ONSITE', 'Présentiel'
        ONLINE = 'ONLINE', 'En ligne'
        HYBRID = 'HYBRID', 'Hybride'

    title = models.CharField('intitulé', max_length=200)
    category = models.CharField('thème', max_length=100, blank=True)
    provider = models.CharField('organisme', max_length=150, blank=True)
    trainer = models.CharField('formateur', max_length=150, blank=True)
    description = models.TextField('programme / objectifs', blank=True)
    start_date = models.DateField('début')
    end_date = models.DateField('fin')
    duration_hours = models.DecimalField('durée (heures)', max_digits=6, decimal_places=1, default=7)
    location = models.CharField('lieu / lien', max_length=200, blank=True)
    mode = models.CharField('format', max_length=10, choices=Mode.choices, default=Mode.ONSITE)
    capacity = models.PositiveSmallIntegerField('places disponibles', null=True, blank=True)
    cost = models.DecimalField('coût total', max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField('statut', max_length=10, choices=Status.choices, default=Status.PLANNED)
    is_open_for_requests = models.BooleanField('ouverte aux demandes des employés', default=True)

    class Meta:
        verbose_name = 'formation'
        verbose_name_plural = 'formations'
        ordering = ['-start_date']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('training:detail', args=[self.pk])

    @property
    def seats_taken(self):
        return self.participants.exclude(status__in=[TrainingParticipant.Status.CANCELLED,
                                                     TrainingParticipant.Status.REQUESTED]).count()

    @property
    def is_full(self):
        return self.capacity is not None and self.seats_taken >= self.capacity


class TrainingParticipant(TimeStampedModel):
    class Status(models.TextChoices):
        REQUESTED = 'REQUESTED', 'Demande en attente'
        REGISTERED = 'REGISTERED', 'Inscrit'
        ATTENDED = 'ATTENDED', 'A suivi'
        ABSENT = 'ABSENT', 'Absent'
        CANCELLED = 'CANCELLED', 'Annulé'

    training = models.ForeignKey(Training, on_delete=models.CASCADE, related_name='participants',
                                 verbose_name='formation')
    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE,
                                 related_name='training_participations', verbose_name='employé')
    status = models.CharField('statut', max_length=10, choices=Status.choices, default=Status.REGISTERED)
    satisfaction = models.PositiveSmallIntegerField('satisfaction (1 à 5)', null=True, blank=True,
                                                    choices=[(i, '★' * i) for i in range(1, 6)])
    feedback = models.TextField('avis', blank=True)
    certificate = models.FileField('attestation', upload_to='formations/attestations/', blank=True,
                                   validators=document_validators)

    class Meta:
        verbose_name = 'participant'
        verbose_name_plural = 'participants'
        ordering = ['employee__last_name']
        constraints = [models.UniqueConstraint(fields=['training', 'employee'], name='unique_training_participant')]

    def __str__(self):
        return f'{self.employee} — {self.training}'
