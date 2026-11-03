"""Moteur de calcul de la paie.

Le calcul est volontairement générique et entièrement paramétrable :
cotisations (PayrollRule), barème d'impôt (TaxBracket) et éléments propres à
chaque employé (SalaryItem). Les taux fournis par défaut doivent être validés
par l'expert-comptable de l'entreprise.
"""
from collections import defaultdict
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum

from attendance.models import OvertimeEntry
from core.company import get_company
from core.utils import month_bounds
from employees.models import Contract, Employee
from leaves.models import LeaveRequest
from leaves.services import holidays_between

from .models import PayrollRule, Payslip, PayslipLine, SalaryItem, TaxBracket

ZERO = Decimal(0)
HUNDRED = Decimal(100)


def round_money(value):
    decimals = get_company().currency_decimals
    quant = Decimal(1) if decimals == 0 else Decimal(1).scaleb(-decimals)
    return Decimal(value).quantize(quant, rounding=ROUND_HALF_UP)


def annual_income_tax(annual_taxable, brackets=None):
    """Impôt annuel selon le barème progressif par tranches."""
    brackets = brackets if brackets is not None else list(TaxBracket.objects.all())
    tax = ZERO
    for bracket in brackets:
        if annual_taxable <= bracket.lower_bound:
            continue
        upper = bracket.upper_bound if bracket.upper_bound is not None else annual_taxable
        taxable_part = min(annual_taxable, upper) - bracket.lower_bound
        if taxable_part > 0:
            tax += taxable_part * bracket.rate / HUNDRED
    return tax


def working_days_in(first, last):
    worked = set(get_company().working_days_list)
    holidays = holidays_between(first, last)
    count, current = 0, first
    while current <= last:
        if current.weekday() in worked and current not in holidays:
            count += 1
        current += timedelta(days=1)
    return count


def contract_for_period(employee, first, last):
    return (employee.contracts
            .filter(status__in=[Contract.Status.ACTIVE, Contract.Status.ENDED, Contract.Status.TERMINATED],
                    start_date__lte=last)
            .filter(Q(end_date__isnull=True) | Q(end_date__gte=first))
            .order_by('-start_date').first())


class PayslipCalculator:
    """Calcule un bulletin étape par étape (brut, cotisations, impôt, net) sans l'enregistrer."""

    def __init__(self, employee, period, contract):
        self.employee = employee
        self.period = period
        self.contract = contract
        self.first, self.last = month_bounds(period.year, period.month)
        self.base_salary = contract.base_salary
        self.lines = []
        self.gross = ZERO
        self.non_taxable = ZERO
        self.deduction_items = []

    def add(self, kind, label, amount, code='', base=None, rate=None, employer_rate=None, employer_amount=ZERO):
        self.lines.append(PayslipLine(kind=kind, code=code, label=label, base=base, rate=rate,
                                      amount=round_money(amount), employer_rate=employer_rate,
                                      employer_amount=round_money(employer_amount),
                                      order=(len(self.lines) + 1) * 10))

    def earn(self, label, amount, code, base=None, taxable=True):
        amount = round_money(amount)
        self.add(PayslipLine.Kind.EARNING, label, amount, code, base=base)
        self.gross += amount
        if not taxable:
            self.non_taxable += amount

    # 1. Salaire de base au prorata des jours de présence dans le mois (base 30 jours).
    def base_pay(self):
        start = max(self.first, self.contract.start_date, self.employee.hire_date)
        end = min([self.last] + [d for d in (self.contract.end_date, self.employee.exit_date) if d])
        days_in_service = max((end - start).days + 1, 0)
        if days_in_service >= (self.last - self.first).days + 1:
            self.days_paid = 30
            self.prorated_base = self.base_salary
            self.earn('Salaire de base', self.prorated_base, 'SB', base=self.base_salary)
        else:
            self.days_paid = min(days_in_service, 30)
            self.prorated_base = self.base_salary * Decimal(self.days_paid) / Decimal(30)
            self.earn(f'Salaire de base (prorata {self.days_paid}/30 jours)', self.prorated_base, 'SB',
                      base=self.base_salary)

    # 2. Primes et indemnités ; les retenues sont mises de côté pour l'étape 6.
    def allowances(self):
        items = SalaryItem.objects.filter(employee=self.employee, is_active=True).filter(
            Q(is_recurring=True) | Q(year=self.period.year, month=self.period.month))
        for item in items:
            if item.kind == SalaryItem.Kind.ALLOWANCE:
                self.earn(item.label, item.amount, 'PRIME', taxable=item.is_taxable)
            else:
                self.deduction_items.append(item)

    # 3. Heures supplémentaires : taux horaire × heures × (1 + majoration), regroupées par type.
    def overtime(self):
        totals = defaultdict(Decimal)
        entries = OvertimeEntry.objects.filter(employee=self.employee, date__range=(self.first, self.last))
        for entry in entries.select_related('overtime_type'):
            totals[entry.overtime_type] += entry.hours
        if not totals:
            return
        monthly_hours = (self.contract.weekly_hours or Decimal(40)) * Decimal(52) / Decimal(12)
        hourly_rate = self.base_salary / monthly_hours
        for overtime_type, hours in sorted(totals.items(), key=lambda item: item[0].order):
            increase = f'{overtime_type.increase_rate.normalize():f}'.replace('.', ',')
            hours_text = f'{hours.normalize():f}'.replace('.', ',')
            self.earn(f'Heures supplémentaires +{increase} % — {overtime_type.name} ({hours_text} h)',
                      hourly_rate * hours * (HUNDRED + overtime_type.increase_rate) / HUNDRED, 'HS',
                      base=round_money(hourly_rate))

    # 4. Absences non rémunérées (congés sans solde approuvés), au prorata des jours ouvrés.
    def unpaid_leave(self):
        self.unpaid_days = ZERO
        leaves = LeaveRequest.objects.filter(
            employee=self.employee, status=LeaveRequest.Status.APPROVED, leave_type__is_paid=False,
            start_date__lte=self.last, end_date__gte=self.first)
        for leave in leaves:
            if leave.half_day:
                self.unpaid_days += Decimal('0.5')
            else:
                self.unpaid_days += Decimal(working_days_in(max(leave.start_date, self.first),
                                                            min(leave.end_date, self.last)))
        if self.unpaid_days:
            expected = working_days_in(self.first, self.last) or 1
            deduction = round_money(self.base_salary * self.unpaid_days / Decimal(expected))
            self.earn(f'Absence non rémunérée ({self.unpaid_days} j)', -deduction, 'ABS')

    # 5. Cotisations sociales (assiette plafonnée, population concernée).
    def contributions(self):
        self.gross = max(self.gross, ZERO)
        self.subject_to_contributions = self.gross - self.non_taxable
        self.employee_contributions = self.employer_contributions = self.deductible = ZERO
        for rule in PayrollRule.objects.filter(is_active=True):
            if not rule.applies_to_employee(self.employee):
                continue
            assiette = (self.subject_to_contributions if rule.base == PayrollRule.Base.GROSS
                        else round_money(self.prorated_base))
            if rule.ceiling is not None:
                assiette = min(assiette, rule.ceiling)
            employee_part = round_money(assiette * rule.employee_rate / HUNDRED)
            employer_part = round_money(assiette * rule.employer_rate / HUNDRED)
            if not employee_part and not employer_part:
                continue
            self.add(PayslipLine.Kind.CONTRIBUTION, rule.name, employee_part, rule.code, base=assiette,
                     rate=rule.employee_rate or None, employer_rate=rule.employer_rate or None,
                     employer_amount=employer_part)
            self.employee_contributions += employee_part
            self.employer_contributions += employer_part
            if rule.is_tax_deductible:
                self.deductible += employee_part

    # 6. Impôt sur le revenu : revenu mensuel annualisé, abattement forfaitaire, puis barème annuel.
    def income_tax(self):
        annual = max(self.subject_to_contributions - self.deductible, ZERO) * 12
        company = get_company()
        allowance = annual * company.tax_allowance_rate / HUNDRED
        if company.tax_allowance_cap is not None:
            allowance = min(allowance, company.tax_allowance_cap)
        self.taxable = round_money((annual - allowance) / 12)
        self.tax = round_money(annual_income_tax(annual - allowance) / 12)
        if self.tax:
            self.add(PayslipLine.Kind.TAX, 'Impôt sur le revenu', self.tax, 'IR', base=self.taxable)

    # 7. Autres retenues (avances, prêts…).
    def other_deductions(self):
        self.other = ZERO
        for item in self.deduction_items:
            self.add(PayslipLine.Kind.DEDUCTION, item.label, item.amount, 'RET')
            self.other += round_money(item.amount)

    def compute(self):
        for step in (self.base_pay, self.allowances, self.overtime, self.unpaid_leave, self.contributions,
                     self.income_tax, self.other_deductions):
            step()
        fields = {
            'base_salary': self.base_salary,
            'days_in_service': self.days_paid,
            'unpaid_leave_days': self.unpaid_days,
            'gross_salary': self.gross,
            'taxable_salary': self.taxable,
            'employee_contributions': self.employee_contributions,
            'employer_contributions': self.employer_contributions,
            'income_tax': self.tax,
            'other_deductions': self.other,
            'net_salary': self.gross - self.employee_contributions - self.tax - self.other,
            'contract_type': self.contract.get_contract_type_display(),
        }
        return fields, self.lines


def compute_payslip(employee, period, contract=None):
    """Calcule un bulletin (non enregistré). Renvoie (champs, lignes)."""
    first, last = month_bounds(period.year, period.month)
    contract = contract or contract_for_period(employee, first, last)
    if contract is None:
        raise ValueError(f'Aucun contrat actif pour {employee} sur {period.label}.')
    return PayslipCalculator(employee, period, contract).compute()


def eligible_employees(period):
    first, last = month_bounds(period.year, period.month)
    return (Employee.objects.filter(hire_date__lte=last)
            .filter(Q(exit_date__isnull=True) | Q(exit_date__gte=first))
            .exclude(status=Employee.Status.SUSPENDED)
            .select_related('position', 'department'))


@transaction.atomic
def generate_period(period):
    """(Re)génère tous les bulletins d'une période en brouillon. Renvoie (créés, [ignorés])."""
    if not period.is_editable:
        raise ValueError('Seule une période en brouillon peut être recalculée.')
    period.payslips.all().delete()
    first, last = month_bounds(period.year, period.month)
    created, skipped = 0, []
    for employee in eligible_employees(period):
        contract = contract_for_period(employee, first, last)
        if contract is None:
            skipped.append(f'{employee} (aucun contrat sur la période)')
            continue
        fields, lines = compute_payslip(employee, period, contract)
        payslip = Payslip.objects.create(
            period=period, employee=employee,
            number=f'BP-{period.year}{period.month:02d}-{employee.employee_id}',
            employee_name=employee.full_name,
            position_title=str(employee.position or ''),
            department_name=str(employee.department or ''),
            **fields,
        )
        for line in lines:
            line.payslip = payslip
        PayslipLine.objects.bulk_create(lines)
        created += 1
    return created, skipped


def period_totals(period):
    return period.payslips.aggregate(
        count=Count('id'), gross=Sum('gross_salary'), net=Sum('net_salary'),
        employee_contributions=Sum('employee_contributions'),
        employer_contributions=Sum('employer_contributions'), income_tax=Sum('income_tax'),
        other_deductions=Sum('other_deductions'),
    )

