from django.conf import settings
from django.db import models
from django.urls import reverse

from core.models import TimeStampedModel
from core.utils import month_label


class PayrollRule(TimeStampedModel):
    """Cotisation sociale (part salariale et/ou patronale) appliquée à tous les bulletins."""

    class Base(models.TextChoices):
        GROSS = 'GROSS', 'Salaire brut'
        BASE = 'BASE', 'Salaire de base'

    class Scope(models.TextChoices):
        ALL = 'ALL', 'Tous les salariés'
        EXECUTIVES = 'EXECUTIVES', 'Cadres uniquement'
        NON_EXECUTIVES = 'NON_EXECUTIVES', 'Non-cadres uniquement'

    code = models.CharField('code', max_length=20, unique=True)
    name = models.CharField('libellé', max_length=150)
    base = models.CharField('assiette', max_length=10, choices=Base.choices, default=Base.GROSS)
    applies_to = models.CharField("s'applique à", max_length=15, choices=Scope.choices, default=Scope.ALL)
    employee_rate = models.DecimalField('taux salarial (%)', max_digits=6, decimal_places=3, default=0)
    employer_rate = models.DecimalField('taux patronal (%)', max_digits=6, decimal_places=3, default=0)
    ceiling = models.DecimalField('plafond mensuel', max_digits=14, decimal_places=2, null=True, blank=True,
                                  help_text="Assiette maximale. Laisser vide s'il n'y a pas de plafond.")
    is_tax_deductible = models.BooleanField('part salariale déductible du revenu imposable', default=True)
    is_active = models.BooleanField('active', default=True)
    order = models.PositiveSmallIntegerField('ordre', default=10)
    notes = models.CharField('notes', max_length=255, blank=True)

    class Meta:
        verbose_name = 'cotisation'
        verbose_name_plural = 'cotisations'
        ordering = ['order', 'code']

    def __str__(self):
        return f'{self.code} — {self.name}'

    def applies_to_employee(self, employee):
        is_executive = bool(employee.position and employee.position.is_executive)
        if self.applies_to == self.Scope.EXECUTIVES:
            return is_executive
        if self.applies_to == self.Scope.NON_EXECUTIVES:
            return not is_executive
        return True


class TaxBracket(models.Model):
    """Tranche du barème annuel de l'impôt sur le revenu."""

    lower_bound = models.DecimalField('de (revenu annuel)', max_digits=14, decimal_places=2)
    upper_bound = models.DecimalField('à (revenu annuel)', max_digits=14, decimal_places=2, null=True, blank=True,
                                      help_text='Laisser vide pour la dernière tranche.')
    rate = models.DecimalField('taux (%)', max_digits=5, decimal_places=2)

    class Meta:
        verbose_name = "tranche d'impôt"
        verbose_name_plural = "barème de l'impôt sur le revenu"
        ordering = ['lower_bound']

    def __str__(self):
        upper = f'{self.upper_bound:,.0f}' if self.upper_bound is not None else '∞'
        return f'{self.lower_bound:,.0f} → {upper} : {self.rate} %'


class SalaryItem(TimeStampedModel):
    """Prime, indemnité ou retenue propre à un employé."""

    class Kind(models.TextChoices):
        ALLOWANCE = 'ALLOWANCE', 'Prime / indemnité'
        DEDUCTION = 'DEDUCTION', 'Retenue (avance, prêt…)'

    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, related_name='salary_items',
                                 verbose_name='employé')
    label = models.CharField('libellé', max_length=150)
    kind = models.CharField('nature', max_length=10, choices=Kind.choices, default=Kind.ALLOWANCE)
    amount = models.DecimalField('montant mensuel', max_digits=12, decimal_places=2)
    is_taxable = models.BooleanField('imposable / soumis à cotisations', default=True,
                                     help_text='Pour les primes uniquement (ex. indemnité de transport : non).')
    is_recurring = models.BooleanField('récurrent (chaque mois)', default=True)
    year = models.PositiveIntegerField('année (si ponctuel)', null=True, blank=True)
    month = models.PositiveSmallIntegerField('mois (si ponctuel)', null=True, blank=True,
                                             choices=[(i, str(i)) for i in range(1, 13)])
    is_active = models.BooleanField('actif', default=True)

    class Meta:
        verbose_name = 'élément de salaire'
        verbose_name_plural = 'éléments de salaire'
        ordering = ['employee__last_name', 'kind', 'label']

    def __str__(self):
        return f'{self.label} — {self.employee}'


class PayrollPeriod(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Brouillon'
        VALIDATED = 'VALIDATED', 'Validée'
        PAID = 'PAID', 'Payée'

    year = models.PositiveIntegerField('année')
    month = models.PositiveSmallIntegerField('mois', choices=[(i, str(i)) for i in range(1, 13)])
    status = models.CharField('statut', max_length=10, choices=Status.choices, default=Status.DRAFT)
    payment_date = models.DateField('date de paiement', null=True, blank=True)
    validated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                     verbose_name='validée par')
    validated_at = models.DateTimeField('validée le', null=True, blank=True)
    notes = models.TextField('notes', blank=True)

    class Meta:
        verbose_name = 'période de paie'
        verbose_name_plural = 'périodes de paie'
        ordering = ['-year', '-month']
        constraints = [models.UniqueConstraint(fields=['year', 'month'], name='unique_payroll_period')]

    def __str__(self):
        return f'Paie {self.label}'

    @property
    def label(self):
        return month_label(self.year, self.month)

    def get_absolute_url(self):
        return reverse('payroll:period_detail', args=[self.pk])

    @property
    def is_editable(self):
        return self.status == self.Status.DRAFT


class Payslip(TimeStampedModel):
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name='payslips',
                               verbose_name='période')
    employee = models.ForeignKey('employees.Employee', on_delete=models.PROTECT, related_name='payslips',
                                 verbose_name='employé')
    number = models.CharField('numéro', max_length=40)
    employee_name = models.CharField('nom', max_length=200)
    position_title = models.CharField('poste', max_length=150, blank=True)
    department_name = models.CharField('département', max_length=120, blank=True)
    contract_type = models.CharField('contrat', max_length=60, blank=True)
    base_salary = models.DecimalField('salaire de base', max_digits=14, decimal_places=2, default=0)
    days_in_service = models.PositiveSmallIntegerField('jours de présence dans le mois', default=30)
    unpaid_leave_days = models.DecimalField('jours d’absence non rémunérée', max_digits=5, decimal_places=1, default=0)
    gross_salary = models.DecimalField('salaire brut', max_digits=14, decimal_places=2, default=0)
    taxable_salary = models.DecimalField('revenu imposable', max_digits=14, decimal_places=2, default=0)
    employee_contributions = models.DecimalField('cotisations salariales', max_digits=14, decimal_places=2, default=0)
    employer_contributions = models.DecimalField('charges patronales', max_digits=14, decimal_places=2, default=0)
    income_tax = models.DecimalField('impôt sur le revenu', max_digits=14, decimal_places=2, default=0)
    other_deductions = models.DecimalField('autres retenues', max_digits=14, decimal_places=2, default=0)
    net_salary = models.DecimalField('net à payer', max_digits=14, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'bulletin de paie'
        verbose_name_plural = 'bulletins de paie'
        ordering = ['-period__year', '-period__month', 'employee_name']
        constraints = [models.UniqueConstraint(fields=['period', 'employee'], name='unique_payslip_per_period')]

    def __str__(self):
        return f'{self.number} — {self.employee_name}'

    def get_absolute_url(self):
        return reverse('payroll:payslip_detail', args=[self.pk])

    @property
    def employer_cost(self):
        return self.gross_salary + self.employer_contributions

    @property
    def total_deductions(self):
        return self.employee_contributions + self.income_tax + self.other_deductions


class PayslipLine(models.Model):
    class Kind(models.TextChoices):
        EARNING = 'EARNING', 'Gain'
        CONTRIBUTION = 'CONTRIBUTION', 'Cotisation'
        TAX = 'TAX', 'Impôt'
        DEDUCTION = 'DEDUCTION', 'Retenue'

    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name='lines')
    kind = models.CharField(max_length=15, choices=Kind.choices)
    code = models.CharField(max_length=20, blank=True)
    label = models.CharField(max_length=200)
    base = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    rate = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    employer_rate = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    employer_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'pk']
        verbose_name = 'ligne de bulletin'
        verbose_name_plural = 'lignes de bulletin'

    def __str__(self):
        return self.label
