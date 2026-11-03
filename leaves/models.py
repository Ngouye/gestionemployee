from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.models import TimeStampedModel
from core.validators import document_validators


class LeaveType(TimeStampedModel):
    name = models.CharField('nom', max_length=100, unique=True)
    code = models.CharField('code', max_length=20, unique=True)
    color = models.CharField('couleur', max_length=7, default='#4f46e5',
                             help_text='Couleur dans le calendrier (ex. #4f46e5).')
    annual_allowance = models.DecimalField('droit annuel (jours)', max_digits=5, decimal_places=1, default=0)
    tracks_balance = models.BooleanField('décompté d’un solde', default=True,
                                         help_text='Si décoché, le congé n’est pas limité par un solde annuel.')
    is_paid = models.BooleanField('rémunéré', default=True)
    requires_attachment = models.BooleanField('justificatif obligatoire', default=False)
    max_carry_over = models.DecimalField('report maximum (jours)', max_digits=5, decimal_places=1, default=0,
                                         help_text="Jours non pris reportables sur l'année suivante.")
    description = models.TextField('description', blank=True)
    is_active = models.BooleanField('actif', default=True)

    class Meta:
        verbose_name = 'type de congé'
        verbose_name_plural = 'types de congé'
        ordering = ['name']

    def __str__(self):
        return self.name


class PublicHoliday(models.Model):
    name = models.CharField('nom', max_length=120)
    date = models.DateField('date')
    is_recurring = models.BooleanField('tous les ans à la même date', default=False)

    class Meta:
        verbose_name = 'jour férié'
        verbose_name_plural = 'jours fériés'
        ordering = ['date']

    def __str__(self):
        return f'{self.name} ({self.date:%d/%m})'


class LeaveBalance(TimeStampedModel):
    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, related_name='leave_balances',
                                 verbose_name='employé')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name='balances',
                                   verbose_name='type de congé')
    year = models.PositiveIntegerField('année')
    allocated = models.DecimalField('jours acquis', max_digits=5, decimal_places=1, default=0)
    carried_over = models.DecimalField('jours reportés', max_digits=5, decimal_places=1, default=0)
    notes = models.CharField('notes', max_length=255, blank=True)

    class Meta:
        verbose_name = 'solde de congés'
        verbose_name_plural = 'soldes de congés'
        ordering = ['-year', 'employee__last_name']
        constraints = [
            models.UniqueConstraint(fields=['employee', 'leave_type', 'year'], name='unique_leave_balance'),
        ]

    def __str__(self):
        return f'{self.employee} — {self.leave_type} {self.year}'

    @property
    def total(self):
        return (self.allocated or Decimal(0)) + (self.carried_over or Decimal(0))


class LeaveRequestQuerySet(models.QuerySet):
    def reviewable_by(self, user):
        pending = self.filter(status=LeaveRequest.Status.PENDING).exclude(employee__user=user)
        if user.is_hr:
            return pending
        return pending.filter(employee__manager__user=user)


class LeaveRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'En attente'
        APPROVED = 'APPROVED', 'Approuvée'
        REJECTED = 'REJECTED', 'Refusée'
        CANCELLED = 'CANCELLED', 'Annulée'

    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, related_name='leave_requests',
                                 verbose_name='employé')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name='requests',
                                   verbose_name='type de congé')
    start_date = models.DateField('du')
    end_date = models.DateField('au')
    half_day = models.BooleanField('demi-journée', default=False)
    days = models.DecimalField('jours ouvrés', max_digits=5, decimal_places=1, default=0)
    reason = models.TextField('motif', blank=True)
    attachment = models.FileField('justificatif', upload_to='conges/justificatifs/%Y/', blank=True,
                                  validators=document_validators)
    status = models.CharField('statut', max_length=10, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='reviewed_leaves', verbose_name='traitée par')
    reviewed_at = models.DateTimeField('traitée le', null=True, blank=True)
    review_comment = models.TextField('commentaire du valideur', blank=True)

    objects = LeaveRequestQuerySet.as_manager()

    class Meta:
        verbose_name = 'demande de congé'
        verbose_name_plural = 'demandes de congé'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', 'start_date'])]

    def __str__(self):
        return f'{self.leave_type} — {self.employee} ({self.start_date:%d/%m/%Y} → {self.end_date:%d/%m/%Y})'

    def get_absolute_url(self):
        return reverse('leaves:detail', args=[self.pk])

    def can_be_reviewed_by(self, user):
        if self.status != self.Status.PENDING or self.employee.user_id == user.pk:
            return False
        return user.is_hr or self.employee.is_managed_by(user)

    def can_be_cancelled_by(self, user):
        if self.employee.user_id != user.pk and not user.is_hr:
            return False
        if self.status == self.Status.PENDING:
            return True
        return self.status == self.Status.APPROVED and self.start_date > timezone.localdate()
