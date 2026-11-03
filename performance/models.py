from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models
from django.urls import reverse

from core.models import TimeStampedModel

RATING_CHOICES = [
    (1, '1 — Insuffisant'), (2, '2 — À améliorer'), (3, '3 — Conforme aux attentes'),
    (4, '4 — Très bien'), (5, '5 — Excellent'),
]


class ReviewCycle(TimeStampedModel):
    class Status(models.TextChoices):
        PLANNED = 'PLANNED', 'Planifiée'
        IN_PROGRESS = 'IN_PROGRESS', 'En cours'
        COMPLETED = 'COMPLETED', 'Clôturée'

    name = models.CharField('nom', max_length=150)
    start_date = models.DateField('début')
    end_date = models.DateField('fin')
    status = models.CharField('statut', max_length=12, choices=Status.choices, default=Status.PLANNED)
    description = models.TextField('description', blank=True)

    class Meta:
        verbose_name = "campagne d'évaluation"
        verbose_name_plural = "campagnes d'évaluation"
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('performance:cycle_detail', args=[self.pk])


class PerformanceReview(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'À réaliser'
        COMPLETED = 'COMPLETED', 'Finalisée'

    cycle = models.ForeignKey(ReviewCycle, on_delete=models.CASCADE, related_name='reviews',
                              verbose_name='campagne')
    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, related_name='reviews',
                                 verbose_name='employé évalué')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='reviews_to_do', verbose_name='évaluateur')
    status = models.CharField('statut', max_length=10, choices=Status.choices, default=Status.PENDING)
    self_assessment = models.TextField("auto-évaluation de l'employé", blank=True)
    quality_rating = models.PositiveSmallIntegerField('qualité du travail', choices=RATING_CHOICES,
                                                      null=True, blank=True)
    productivity_rating = models.PositiveSmallIntegerField('productivité', choices=RATING_CHOICES,
                                                           null=True, blank=True)
    teamwork_rating = models.PositiveSmallIntegerField("esprit d'équipe", choices=RATING_CHOICES,
                                                       null=True, blank=True)
    initiative_rating = models.PositiveSmallIntegerField('initiative et autonomie', choices=RATING_CHOICES,
                                                         null=True, blank=True)
    overall_rating = models.PositiveSmallIntegerField('appréciation globale', choices=RATING_CHOICES,
                                                      null=True, blank=True)
    strengths = models.TextField('points forts', blank=True)
    improvements = models.TextField("axes d'amélioration", blank=True)
    next_goals = models.TextField('objectifs pour la période suivante', blank=True)
    reviewer_comments = models.TextField("commentaire de l'évaluateur", blank=True)
    employee_comments = models.TextField("commentaire de l'employé", blank=True)
    completed_at = models.DateTimeField('finalisée le', null=True, blank=True)

    class Meta:
        verbose_name = 'évaluation'
        verbose_name_plural = 'évaluations'
        ordering = ['-cycle__start_date', 'employee__last_name']
        constraints = [models.UniqueConstraint(fields=['cycle', 'employee'], name='unique_review_per_cycle')]

    def __str__(self):
        return f'{self.cycle} — {self.employee}'

    def get_absolute_url(self):
        return reverse('performance:review_detail', args=[self.pk])

    @property
    def criteria(self):
        return [(self._meta.get_field(name).verbose_name, getattr(self, name))
                for name in ('quality_rating', 'productivity_rating', 'teamwork_rating', 'initiative_rating')]


class Objective(TimeStampedModel):
    class Status(models.TextChoices):
        NOT_STARTED = 'NOT_STARTED', 'Non démarré'
        IN_PROGRESS = 'IN_PROGRESS', 'En cours'
        ACHIEVED = 'ACHIEVED', 'Atteint'
        MISSED = 'MISSED', 'Non atteint'

    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, related_name='objectives',
                                 verbose_name='employé')
    cycle = models.ForeignKey(ReviewCycle, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='objectives', verbose_name='campagne')
    title = models.CharField('objectif', max_length=200)
    description = models.TextField('description / indicateurs', blank=True)
    due_date = models.DateField('échéance', null=True, blank=True)
    progress = models.PositiveSmallIntegerField('avancement (%)', default=0, validators=[MaxValueValidator(100)])
    status = models.CharField('statut', max_length=12, choices=Status.choices, default=Status.NOT_STARTED)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name='fixé par')

    class Meta:
        verbose_name = 'objectif'
        verbose_name_plural = 'objectifs'
        ordering = ['status', 'due_date']

    def __str__(self):
        return self.title
