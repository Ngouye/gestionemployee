from datetime import date
from decimal import Decimal

from django.urls import reverse

from attendance.models import OvertimeEntry, OvertimeType
from core.models import Notification
from employees.models import Contract, Employee
from payroll.models import PayrollPeriod
from payroll.services import compute_payslip

from .base import DemoDataTestCase


class OvertimePayrollTests(DemoDataTestCase):
    def setUp(self):
        self.period = PayrollPeriod.objects.create(year=2030, month=2)
        self.employee = Employee.objects.create(first_name='Heures', last_name='Sup', email='hs@demo.sn',
                                                hire_date=date(2029, 1, 1))
        Contract.objects.create(employee=self.employee, start_date=date(2029, 1, 1), base_salary=Decimal(520000),
                                weekly_hours=40)
        self.type15 = OvertimeType.objects.get(code='HS15')

    def test_overtime_is_paid_with_increase(self):
        OvertimeEntry.objects.create(employee=self.employee, date=date(2030, 2, 10), hours=Decimal(4),
                                     overtime_type=self.type15)
        OvertimeEntry.objects.create(employee=self.employee, date=date(2030, 2, 11), hours=Decimal(2),
                                     overtime_type=self.type15)
        OvertimeEntry.objects.create(employee=self.employee, date=date(2030, 3, 1), hours=Decimal(5),
                                     overtime_type=self.type15)  # hors période
        fields, lines = compute_payslip(self.employee, self.period)
        line = next(line for line in lines if line.code == 'HS')
        # taux horaire = 520 000 / (40 × 52 / 12) = 3 000 ; 6 h × 3 000 × 1,15 = 20 700
        self.assertEqual(line.amount, Decimal(20700))
        self.assertIn('(6 h)', line.label)
        self.assertIn('+15 %', line.label)
        self.assertEqual(fields['gross_salary'], Decimal(520000) + Decimal(20700))

    def test_entry_refused_when_payroll_validated(self):
        PayrollPeriod.objects.create(year=2031, month=5, status=PayrollPeriod.Status.VALIDATED)
        self.login(self.hr)
        response = self.client.post(reverse('attendance:overtime_create'), {
            'employee': self.employee.pk, 'date': '2031-05-10', 'overtime_type': self.type15.pk, 'hours': '2'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'déjà validée')
        self.assertFalse(OvertimeEntry.objects.filter(date=date(2031, 5, 10)).exists())

    def test_manager_limited_to_team(self):
        self.login(self.manager)
        outsider = Employee.objects.exclude(manager=self.manager.employee).exclude(pk=self.manager.employee.pk).first()
        response = self.client.post(reverse('attendance:overtime_create'), {
            'employee': outsider.pk, 'date': '2031-06-10', 'overtime_type': self.type15.pk, 'hours': '2'})
        self.assertEqual(response.status_code, 200)  # formulaire invalide : employé hors équipe
        self.assertFalse(OvertimeEntry.objects.filter(employee=outsider, date=date(2031, 6, 10)).exists())
        member = self.manager.employee.subordinates.first()
        self.client.post(reverse('attendance:overtime_create'), {
            'employee': member.pk, 'date': '2031-06-10', 'overtime_type': self.type15.pk, 'hours': '2'})
        self.assertTrue(OvertimeEntry.objects.filter(employee=member, date=date(2031, 6, 10)).exists())

    def test_employee_cannot_access_overtime_management(self):
        self.login(self.employee_user)
        self.assertEqual(self.client.get(reverse('attendance:overtime_list')).status_code, 403)
        self.assertEqual(self.client.get(reverse('attendance:mine')).status_code, 200)


class EmploymentLetterTests(DemoDataTestCase):
    def test_hr_generates_attestation(self):
        self.login(self.hr)
        employee = self.employee_user.employee
        response = self.client.get(reverse('employees:work_attestation', args=[employee.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_certificate_requires_exit_date(self):
        self.login(self.hr)
        active = self.employee_user.employee
        response = self.client.get(reverse('employees:work_certificate', args=[active.pk]))
        self.assertEqual(response.status_code, 302)
        former = Employee.objects.filter(exit_date__isnull=False).first()
        response = self.client.get(reverse('employees:work_certificate', args=[former.pk]))
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_employee_requests_but_cannot_generate(self):
        self.login(self.employee_user)
        employee = self.employee_user.employee
        self.assertEqual(self.client.get(reverse('employees:work_attestation', args=[employee.pk])).status_code, 403)
        self.client.post(reverse('employees:request_attestation'))
        self.assertTrue(Notification.objects.filter(user=self.hr, title__contains='attestation').exists())
