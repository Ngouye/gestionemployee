from django.conf import settings
from django.db import models
from django.urls import reverse

from core.models import TimeStampedModel
from core.validators import document_validators


class ExpenseCategory(TimeStampedModel):
    name = models.CharField('nom', max_length=100, unique=True)
    description = models.CharField('description', max_length=255, blank=True)
    max_amount = models.DecimalField('plafond par note', max_digits=12, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField('active', default=True)

    class Meta:
        verbose_name = 'catégorie de frais'
        verbose_name_plural = 'catégories de frais'
        ordering = ['name']

    def __str__(self):
        return self.name


class ExpenseClaimQuerySet(models.QuerySet):
    def reviewable_by(self, user):
        submitted = self.filter(status=ExpenseClaim.Status.SUBMITTED).exclude(employee__user=user)
        if user.is_hr:
            return submitted
        return submitted.filter(employee__manager__user=user)


class ExpenseClaim(TimeStampedModel):
    class Status(models.TextChoices):
        SUBMITTED = 'SUBMITTED', 'Soumise'
        APPROVED = 'APPROVED', 'Approuvée'
        REJECTED = 'REJECTED', 'Refusée'
        PAID = 'PAID', 'Remboursée'

    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, related_name='expense_claims',
                                 verbose_name='employé')
    title = models.CharField('objet', max_length=200)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='claims',
                                 verbose_name='catégorie')
    expense_date = models.DateField('date de la dépense')
    amount = models.DecimalField('montant', max_digits=12, decimal_places=2)
    description = models.TextField('détails', blank=True)
    receipt = models.FileField('justificatif', upload_to='notes-de-frais/%Y/%m/', blank=True,
                               validators=document_validators)
    status = models.CharField('statut', max_length=10, choices=Status.choices, default=Status.SUBMITTED)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='reviewed_expenses', verbose_name='traitée par')
    reviewed_at = models.DateTimeField('traitée le', null=True, blank=True)
    review_comment = models.TextField('commentaire', blank=True)
    paid_at = models.DateField('remboursée le', null=True, blank=True)

    objects = ExpenseClaimQuerySet.as_manager()

    class Meta:
        verbose_name = 'note de frais'
        verbose_name_plural = 'notes de frais'
        ordering = ['-expense_date', '-created_at']

    def __str__(self):
        return f'{self.title} — {self.employee}'

    def get_absolute_url(self):
        return reverse('expenses:detail', args=[self.pk])

    def can_be_reviewed_by(self, user):
        if self.status != self.Status.SUBMITTED or self.employee.user_id == user.pk:
            return False
        return user.is_hr or self.employee.is_managed_by(user)
