"""Contrôles d'accès, verrouillage de connexion et confidentialité des fichiers."""
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from core.models import AuditLog
from employees.models import Employee, EmployeeDocument
from payroll.models import PayrollPeriod, Payslip

from .base import PASSWORD, DemoDataTestCase


class AccessControlTests(DemoDataTestCase):
    def test_employee_cannot_see_colleague_profile(self):
        self.login(self.employee_user)
        colleague = Employee.objects.exclude(user=self.employee_user).exclude(
            pk=self.employee_user.employee.manager_id).first()
        response = self.client.get(reverse('employees:detail', args=[colleague.pk]))
        self.assertEqual(response.status_code, 403)

    def test_employee_sees_own_profile(self):
        self.login(self.employee_user)
        response = self.client.get(reverse('employees:my_profile'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.employee_user.employee.full_name)

    def test_manager_sees_team_member_but_not_salary_tab(self):
        self.login(self.manager)
        member = self.manager.employee.subordinates.first()
        response = self.client.get(reverse('employees:detail', args=[member.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-bs-target="#paie"')

    def test_employee_cannot_open_someone_else_payslip(self):
        self.login(self.employee_user)
        other = Payslip.objects.exclude(employee__user=self.employee_user).exclude(
            period__status=PayrollPeriod.Status.DRAFT).first()
        self.assertEqual(self.client.get(reverse('payroll:payslip_pdf', args=[other.pk])).status_code, 403)
        own = Payslip.objects.filter(employee__user=self.employee_user).exclude(
            period__status=PayrollPeriod.Status.DRAFT).first()
        response = self.client.get(reverse('payroll:payslip_pdf', args=[own.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_draft_payslip_hidden_from_employee(self):
        self.login(self.employee_user)
        draft = Payslip.objects.filter(employee__user=self.employee_user,
                                       period__status=PayrollPeriod.Status.DRAFT).first()
        self.assertEqual(self.client.get(reverse('payroll:payslip_detail', args=[draft.pk])).status_code, 403)

    def test_api_requires_authentication(self):
        self.assertIn(self.client.get('/api/v1/employes/').status_code, (401, 403))

    def test_open_redirect_is_blocked(self):
        self.login(self.employee_user)
        response = self.client.post(reverse('core:notifications_mark_all'), {'next': 'https://evil.example.com/'})
        self.assertEqual(response['Location'], reverse('core:notifications'))


class AuthenticationTests(DemoDataTestCase):
    def setUp(self):
        cache.clear()

    def test_login_with_email(self):
        response = self.client.post(reverse('accounts:login'), {'username': 'RH@demo.sn', 'password': PASSWORD})
        self.assertRedirects(response, reverse('core:dashboard'), fetch_redirect_response=False)
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.LOGIN, user=self.hr).exists())

    def test_lockout_after_failed_attempts(self):
        for _ in range(5):
            self.client.post(reverse('accounts:login'), {'username': 'rh@demo.sn', 'password': 'mauvais'})
        response = self.client.post(reverse('accounts:login'), {'username': 'rh@demo.sn', 'password': PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Trop de tentatives')
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.LOGIN_FAILED).exists())

    def test_temporary_password_forces_change(self):
        user = get_user_model().objects.create_user(email='nouveau@demo.sn', password='Temp0raire!x',
                                                    must_change_password=True)
        self.login(user)
        response = self.client.get(reverse('core:dashboard'))
        self.assertRedirects(response, reverse('accounts:password_change'))
        response = self.client.post(reverse('accounts:password_change'), {
            'old_password': 'Temp0raire!x', 'new_password1': 'Nouv3au-Mot-de-Passe', 'new_password2':
            'Nouv3au-Mot-de-Passe'})
        self.assertRedirects(response, reverse('core:dashboard'), fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertFalse(user.must_change_password)

    def test_logout_requires_post(self):
        self.login(self.hr)
        self.assertEqual(self.client.get(reverse('accounts:logout')).status_code, 405)
        self.assertEqual(self.client.post(reverse('accounts:logout')).status_code, 302)


class ProtectedFileTests(DemoDataTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media = tempfile.mkdtemp()
        cls.override = override_settings(MEDIA_ROOT=cls.media)
        cls.override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        shutil.rmtree(cls.media, ignore_errors=True)
        super().tearDownClass()

    def test_documents_are_private(self):
        employee = self.employee_user.employee
        self.login(self.hr)
        upload = SimpleUploadedFile('attestation.pdf', b'%PDF-1.4 test', content_type='application/pdf')
        self.client.post(reverse('employees:document_upload', args=[employee.pk]), {
            'title': 'Attestation de travail', 'category': 'ADMIN', 'file': upload, 'visible_to_employee': 'on'})
        hidden = SimpleUploadedFile('note.pdf', b'%PDF-1.4 rh', content_type='application/pdf')
        self.client.post(reverse('employees:document_upload', args=[employee.pk]), {
            'title': 'Note RH', 'category': 'OTHER', 'file': hidden})
        visible_doc = EmployeeDocument.objects.get(title='Attestation de travail')
        hidden_doc = EmployeeDocument.objects.get(title='Note RH')

        self.login(self.employee_user)
        self.assertEqual(self.client.get(reverse('employees:document_download', args=[visible_doc.pk])).status_code,
                         200)
        self.assertEqual(self.client.get(reverse('employees:document_download', args=[hidden_doc.pk])).status_code,
                         403)
        self.login(self.admin.__class__.objects.create_user(email='autre@demo.sn', password='x'))
        self.assertEqual(self.client.get(reverse('employees:document_download', args=[visible_doc.pk])).status_code,
                         403)

    def test_rejects_dangerous_extension(self):
        employee = self.employee_user.employee
        self.login(self.hr)
        upload = SimpleUploadedFile('script.html', b'<script>alert(1)</script>', content_type='text/html')
        self.client.post(reverse('employees:document_upload', args=[employee.pk]), {
            'title': 'Piège', 'category': 'OTHER', 'file': upload})
        self.assertFalse(EmployeeDocument.objects.filter(title='Piège').exists())
