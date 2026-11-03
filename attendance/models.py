from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models

from core.company import get_company
from core.models import TimeStampedModel


class Attendance(TimeStampedModel):
    class Status(models.TextChoices):
        PRESENT = 'PRESENT', 'Présent'
        LATE = 'LATE', 'En retard'
        REMOTE = 'REMOTE', 'Télétravail'
        HALF_DAY = 'HALF_DAY', 'Demi-journée'
        ABSENT = 'ABSENT', 'Absent'
        ON_LEAVE = 'ON_LEAVE', 'En congé'

    class Source(models.TextChoices):
        SELF = 'SELF', 'Pointage employé'
        MANUAL = 'MANUAL', 'Saisie RH'

    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, related_name='attendances',
                                 verbose_name='employé')
    date = models.DateField('date')
    check_in = models.TimeField('arrivée', null=True, blank=True)
    check_out = models.TimeField('départ', null=True, blank=True)
    status = models.CharField('statut', max_length=10, choices=Status.choices, default=Status.PRESENT)
    source = models.CharField('source', max_length=10, choices=Source.choices, default=Source.MANUAL)
    note = models.CharField('remarque', max_length=255, blank=True)
    ip_address = models.GenericIPAddressField('adresse IP', null=True, blank=True)

    class Meta:
        verbose_name = 'présence'
        verbose_name_plural = 'présences'
        ordering = ['-date', 'employee__last_name']
        constraints = [models.UniqueConstraint(fields=['employee', 'date'], name='unique_attendance_per_day')]

    def __str__(self):
        return f'{self.employee} — {self.date:%d/%m/%Y}'

    @property
    def worked_hours(self):
        if not (self.check_in and self.check_out):
            return None
        start = datetime.combine(self.date, self.check_in)
        end = datetime.combine(self.date, self.check_out)
        if end <= start:
            return Decimal(0)
        return (Decimal((end - start).total_seconds()) / Decimal(3600)).quantize(Decimal('0.01'))

    @staticmethod
    def status_for_arrival(arrival, company):
        limit = (datetime.combine(datetime.today(), company.work_start)
                 + timedelta(minutes=company.late_tolerance_minutes)).time()
        return Attendance.Status.LATE if arrival > limit else Attendance.Status.PRESENT

    @property
    def late_minutes(self):
        if self.status != self.Status.LATE or not self.check_in:
            return 0
        start = datetime.combine(self.date, get_company().work_start)
        return max(0, int((datetime.combine(self.date, self.check_in) - start).total_seconds() // 60))


class OvertimeType(models.Model):
    """Catégorie d'heures supplémentaires et sa majoration (paramétrable)."""

    name = models.CharField('libellé', max_length=120)
    code = models.CharField('code', max_length=20, unique=True)
    increase_rate = models.DecimalField('majoration (%)', max_digits=5, decimal_places=2,
                                        help_text='Ex. 15 pour une heure payée 115 % du taux horaire.')
    is_active = models.BooleanField('actif', default=True)
    order = models.PositiveSmallIntegerField('ordre', default=10)

    class Meta:
        verbose_name = "type d'heures supplémentaires"
        verbose_name_plural = "types d'heures supplémentaires"
        ordering = ['order', 'name']

    def __str__(self):
        return f'{self.name} (+{self.increase_rate.normalize():f} %)'


class OvertimeEntry(TimeStampedModel):
    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, related_name='overtime_entries',
                                 verbose_name='employé')
    date = models.DateField('date')
    overtime_type = models.ForeignKey(OvertimeType, on_delete=models.PROTECT, related_name='entries',
                                      verbose_name='type')
    hours = models.DecimalField('nombre d’heures', max_digits=5, decimal_places=2)
    note = models.CharField('motif', max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name='saisi par')

    class Meta:
        verbose_name = 'heures supplémentaires'
        verbose_name_plural = 'heures supplémentaires'
        ordering = ['-date', 'employee__last_name']

    def __str__(self):
        return f'{self.employee} — {self.hours} h le {self.date:%d/%m/%Y}'
