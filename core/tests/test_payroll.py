from datetime import date
from decimal import Decimal

from django.urls import reverse

from core.models import CompanySettings
from employees.models import Contract, Employee
from organization.models import Position
from payroll.models import PayrollPeriod, PayrollRule, SalaryItem, TaxBracket
from payroll.services import annual_income_tax, compute_payslip, eligible_employees, generate_period

from .base import DemoDataTestCase


class TaxTests(DemoDataTestCase):
    def test_progressive_brackets(self):
        brackets = list(TaxBracket.objects.all())
        self.assertEqual(annual_income_tax(Decimal(600000), brackets), Decimal(0))
        # 630 000 → 1 500 000 à 20 % = 174 000 ; 1 500 000 → 2 000 000 à 30 % = 150 000
        self.assertEqual(annual_income_tax(Decimal(2000000), brackets), Decimal(324000))


class PayslipComputationTests(DemoDataTestCase):
    def setUp(self):
        self.period = PayrollPeriod.objects.create(year=2030, month=1)
        self.employee = Employee.objects.create(first_name='Test', last_name='Paie', email='paie@demo.sn',
                                                hire_date=date(2029, 1, 1))
        Contract.objects.create(employee=self.employee, start_date=date(2029, 1, 1), base_salary=Decimal(500000))

    def test_net_is_gross_minus_deductions(self):
        SalaryItem.objects.create(employee=self.employee, label='Transport', amount=26000, is_taxable=False)
        fields, lines = compute_payslip(self.employee, self.period)
        self.assertEqual(fields['gross_salary'], Decimal(526000))
        expected_net = (fields['gross_salary'] - fields['employee_contributions'] - fields['income_tax']
                        - fields['other_deductions'])
        self.assertEqual(fields['net_salary'], expected_net)
        # La prime non imposable n'entre pas dans l'assiette des cotisations
        ipres = next(line for line in lines if line.code == 'IPRES_RG')
        self.assertEqual(ipres.base, Decimal(432000))  # plafond
        self.assertEqual(ipres.amount, Decimal('24192'))  # 432 000 × 5,6 %

    def test_executive_only_rule(self):
        _fields, lines = compute_payslip(self.employee, self.period)
        self.assertFalse(any(line.code == 'IPRES_RC' for line in lines))
        self.employee.position = Position.objects.create(title='Cadre test', is_executive=True)
        self.employee.save()
        _fields, lines = compute_payslip(self.employee, self.period)
        self.assertTrue(any(line.code == 'IPRES_RC' for line in lines))

    def test_proration_for_mid_month_hire(self):
        self.employee.hire_date = date(2030, 1, 16)
        self.employee.save()
        self.employee.contracts.update(start_date=date(2030, 1, 16))
        fields, _lines = compute_payslip(self.employee, self.period)
        self.assertEqual(fields['days_in_service'], 16)
        self.assertEqual(fields['gross_salary'], Decimal(266667))  # 500 000 × 16/30, arrondi

    def test_tax_allowance_is_capped(self):
        company = CompanySettings.load()
        company.tax_allowance_rate, company.tax_allowance_cap = Decimal(0), None
        company.save()
        without, _lines = compute_payslip(self.employee, self.period)
        company.tax_allowance_rate, company.tax_allowance_cap = Decimal(30), Decimal(900000)
        company.save()
        with_allowance, _lines = compute_payslip(self.employee, self.period)
        # 30 % du revenu annuel dépasse le plafond : l'abattement est de 900 000 / an, soit 75 000 / mois
        self.assertEqual(without['taxable_salary'] - with_allowance['taxable_salary'], Decimal(75000))
        self.assertLess(with_allowance['income_tax'], without['income_tax'])

    def test_rule_ceiling_and_deductions(self):
        PayrollRule.objects.update(is_active=False)
        PayrollRule.objects.create(code='T', name='Test', employee_rate=10, employer_rate=20, ceiling=100000)
        SalaryItem.objects.create(employee=self.employee, label='Avance', kind=SalaryItem.Kind.DEDUCTION,
                                  amount=20000)
        fields, _lines = compute_payslip(self.employee, self.period)
        self.assertEqual(fields['employee_contributions'], Decimal(10000))
        self.assertEqual(fields['employer_contributions'], Decimal(20000))
        self.assertEqual(fields['other_deductions'], Decimal(20000))


class PayrollWorkflowTests(DemoDataTestCase):
    def test_generate_validate_and_pay(self):
        self.login(self.hr)
        period = PayrollPeriod.objects.create(year=2031, month=3)
        created, skipped = generate_period(period)
        self.assertGreater(created, 0)
        self.assertEqual(created + len(skipped), eligible_employees(period).count())
        self.client.post(reverse('payroll:period_validate', args=[period.pk]))
        period.refresh_from_db()
        self.assertEqual(period.status, PayrollPeriod.Status.VALIDATED)
        with self.assertRaises(ValueError):
            generate_period(period)
        self.client.post(reverse('payroll:period_pay', args=[period.pk]))
        period.refresh_from_db()
        self.assertEqual(period.status, PayrollPeriod.Status.PAID)

    def test_hr_cannot_reopen_but_admin_can(self):
        period = PayrollPeriod.objects.filter(status=PayrollPeriod.Status.PAID).first()
        self.login(self.hr)
        self.assertEqual(self.client.post(reverse('payroll:period_reopen', args=[period.pk])).status_code, 403)
        self.login(self.admin)
        self.client.post(reverse('payroll:period_reopen', args=[period.pk]))
        period.refresh_from_db()
        self.assertEqual(period.status, PayrollPeriod.Status.DRAFT)
