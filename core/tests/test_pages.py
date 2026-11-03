"""Test de fumée : chaque page s'affiche pour les rôles autorisés et est refusée aux autres."""
from django.urls import reverse

from employees.models import Contract, Employee
from expenses.models import ExpenseClaim
from leaves.models import LeaveBalance, LeaveRequest
from payroll.models import PayrollPeriod, Payslip
from performance.models import PerformanceReview, ReviewCycle
from recruitment.models import Application, Interview, JobOpening
from training.models import Training

from .base import DemoDataTestCase

EVERYONE = [
    'core:dashboard', 'core:notifications', 'core:announcements', 'employees:directory', 'employees:org_chart',
    'leaves:my_leaves', 'leaves:create', 'leaves:calendar', 'attendance:mine', 'payroll:my_payslips',
    'expenses:mine', 'expenses:create', 'performance:mine', 'performance:objective_list', 'training:mine',
    'accounts:profile', 'accounts:password_change', 'recruitment:interview_list',
]

HR_ONLY = [
    'employees:list', 'employees:create', 'employees:import', 'employees:contract_list',
    'organization:department_list', 'organization:department_create', 'organization:position_list',
    'organization:position_create', 'leaves:list', 'leaves:hr_create', 'leaves:balances', 'leaves:type_list',
    'leaves:type_create', 'leaves:holiday_list', 'leaves:holiday_create', 'attendance:create',
    'payroll:period_list', 'payroll:period_create', 'payroll:rule_list', 'payroll:rule_create',
    'payroll:bracket_list', 'payroll:bracket_create', 'payroll:item_list', 'payroll:item_create',
    'expenses:list', 'expenses:category_list', 'expenses:category_create', 'recruitment:job_list',
    'recruitment:job_create', 'recruitment:application_list', 'recruitment:application_create',
    'performance:cycle_list', 'performance:cycle_create', 'training:list', 'training:create',
    'core:announcement_admin', 'core:announcement_create',
]

ADMIN_ONLY = ['accounts:user_list', 'accounts:user_create', 'core:settings', 'core:audit_log']

PUBLIC = ['accounts:login', 'accounts:password_reset', 'recruitment:careers_list']


class PageSmokeTests(DemoDataTestCase):
    def assertPages(self, names, status):
        for name in names:
            url = reverse(name)
            response = self.client.get(url)
            self.assertEqual(response.status_code, status, f'{name} ({url}) → {response.status_code}')

    def test_public_pages(self):
        self.assertPages(PUBLIC, 200)
        job = JobOpening.objects.filter(status=JobOpening.Status.OPEN).first()
        self.assertEqual(self.client.get(reverse('recruitment:careers_detail', args=[job.pk])).status_code, 200)

    def test_anonymous_is_redirected_to_login(self):
        for name in ['core:dashboard', 'employees:list', 'payroll:period_list', 'leaves:my_leaves']:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn(reverse('accounts:login'), response['Location'])

    def test_admin_sees_everything(self):
        self.login(self.admin)
        self.assertPages(EVERYONE + HR_ONLY + ADMIN_ONLY, 200)

    def test_hr_pages(self):
        self.login(self.hr)
        self.assertPages(EVERYONE + HR_ONLY, 200)
        self.assertPages(ADMIN_ONLY, 403)

    def test_employee_pages(self):
        self.login(self.employee_user)
        self.assertPages(EVERYONE, 200)
        self.assertPages(HR_ONLY + ADMIN_ONLY, 403)

    def test_manager_team_pages(self):
        self.login(self.manager)
        self.assertPages(EVERYONE + ['employees:list', 'attendance:register', 'attendance:report',
                                     'core:approvals', 'performance:objective_create'], 200)
        self.assertPages(['payroll:period_list', 'employees:create', 'leaves:balances'], 403)

    def test_detail_pages_for_hr(self):
        self.login(self.hr)
        employee = Employee.objects.filter(user__isnull=False).first()
        period = PayrollPeriod.objects.first()
        job = JobOpening.objects.first()
        application = Application.objects.first()
        objects = [
            ('employees:detail', employee.pk), ('employees:update', employee.pk), ('employees:delete', employee.pk),
            ('employees:contract_create', employee.pk),
            ('employees:contract_update', Contract.objects.first().pk),
            ('leaves:detail', LeaveRequest.objects.first().pk),
            ('leaves:balance_update', LeaveBalance.objects.first().pk),
            ('payroll:period_detail', period.pk), ('payroll:payslip_detail', Payslip.objects.first().pk),
            ('payroll:payslip_pdf', Payslip.objects.first().pk),
            ('expenses:detail', ExpenseClaim.objects.first().pk),
            ('recruitment:job_detail', job.pk), ('recruitment:job_update', job.pk),
            ('recruitment:application_detail', application.pk),
            ('recruitment:application_update', application.pk),
            ('recruitment:interview_feedback', Interview.objects.first().pk),
            ('performance:cycle_detail', ReviewCycle.objects.first().pk),
            ('performance:review_detail', PerformanceReview.objects.first().pk),
            ('training:detail', Training.objects.first().pk),
        ]
        for name, pk in objects:
            response = self.client.get(reverse(name, args=[pk]))
            self.assertEqual(response.status_code, 200, f'{name}({pk}) → {response.status_code}')

    def test_exports(self):
        self.login(self.hr)
        for name in ['employees:list', 'employees:contract_list', 'leaves:list', 'expenses:list',
                     'recruitment:application_list', 'training:list', 'payroll:item_list']:
            for fmt in ('xlsx', 'csv'):
                response = self.client.get(reverse(name), {'export': fmt})
                self.assertEqual(response.status_code, 200, f'{name} {fmt}')
                self.assertIn('attachment', response['Content-Disposition'])
        period = PayrollPeriod.objects.first()
        for export in ('livre', 'virements'):
            response = self.client.get(reverse('payroll:period_detail', args=[period.pk]), {'export': export})
            self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('attendance:report'), {'export': 'xlsx'})
        self.assertEqual(response.status_code, 200)
