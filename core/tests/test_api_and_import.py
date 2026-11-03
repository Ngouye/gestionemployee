from datetime import date, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from employees.models import Employee
from leaves.models import LeaveRequest, LeaveType

from .base import PASSWORD, DemoDataTestCase


class ApiTests(DemoDataTestCase):
    def setUp(self):
        self.api = APIClient()

    def test_token_authentication_and_me(self):
        response = self.api.post('/api/v1/jeton/', {'username': 'employe@demo.sn', 'password': PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.api.credentials(HTTP_AUTHORIZATION=f"Token {response.json()['token']}")
        me = self.api.get('/api/v1/moi/').json()
        self.assertEqual(me['email'], 'employe@demo.sn')
        self.assertTrue(me['leave_balances'])

    def test_employee_directory_hides_sensitive_fields(self):
        self.api.force_authenticate(self.employee_user)
        data = self.api.get('/api/v1/employes/').json()
        self.assertNotIn('bank_account', data['results'][0])
        self.api.force_authenticate(self.hr)
        data = self.api.get('/api/v1/employes/').json()
        self.assertIn('bank_account', data['results'][0])

    def test_only_hr_can_write(self):
        self.api.force_authenticate(self.employee_user)
        self.assertEqual(self.api.post('/api/v1/departements/', {'name': 'Nouveau'}).status_code, 403)
        self.api.force_authenticate(self.hr)
        self.assertEqual(self.api.post('/api/v1/departements/', {'name': 'Nouveau'}).status_code, 201)

    def test_create_leave_request(self):
        Token.objects.create(user=self.employee_user)
        self.api.force_authenticate(self.employee_user)
        start = date.today() + timedelta(days=90)
        start += timedelta(days=(7 - start.weekday()) % 7)
        response = self.api.post('/api/v1/conges/', {
            'leave_type': LeaveType.objects.get(code='CA').pk, 'start_date': start.isoformat(),
            'end_date': (start + timedelta(days=2)).isoformat()})
        self.assertEqual(response.status_code, 201, response.content)
        leave = LeaveRequest.objects.get(pk=response.json()['id'])
        self.assertEqual(leave.employee.user, self.employee_user)
        self.assertEqual(leave.status, LeaveRequest.Status.PENDING)


class ImportTests(DemoDataTestCase):
    def test_csv_import(self):
        self.login(self.hr)
        content = ('prenom;nom;email;date_embauche;departement;poste;type_contrat;salaire_base\n'
                   'Awa;Test;awa.test@demo.sn;01/02/2024;Logistique;Magasinier;CDI;300000\n'
                   'Sans;Email;;01/02/2024;;;CDI;\n').encode('utf-8')
        upload = SimpleUploadedFile('employes.csv', content, content_type='text/csv')
        response = self.client.post(reverse('employees:import'), {'file': upload})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['report']['created'], 1)
        self.assertEqual(len(response.context['report']['errors']), 1)
        employee = Employee.objects.get(email='awa.test@demo.sn')
        self.assertEqual(employee.department.name, 'Logistique')
        self.assertEqual(employee.base_salary, 300000)

    def test_import_template_download(self):
        self.login(self.hr)
        response = self.client.get(reverse('employees:import'), {'modele': 1})
        self.assertEqual(response.status_code, 200)
        self.assertIn('spreadsheetml', response['Content-Type'])


class EmployeeCreationTests(DemoDataTestCase):
    def test_create_employee_with_contract_and_account(self):
        self.login(self.hr)
        response = self.client.post(reverse('employees:create'), {
            'first_name': 'Nouvel', 'last_name': 'Arrivant', 'email': 'nouvel.arrivant@demo.sn',
            'hire_date': date.today().isoformat(), 'status': 'ACTIVE', 'nationality': 'Sénégalaise',
            'children_count': 0, 'tax_shares': 1, 'payment_method': 'TRANSFER',
            'contract-contract_type': 'CDI', 'contract-base_salary': 450000, 'contract-weekly_hours': 40,
            'account-create_account': 'on', 'account-role': 'EMPLOYEE',
        })
        employee = Employee.objects.get(email='nouvel.arrivant@demo.sn')
        self.assertRedirects(response, employee.get_absolute_url(), fetch_redirect_response=False)
        self.assertTrue(employee.employee_id.startswith('EMP-'))
        self.assertEqual(employee.base_salary, 450000)
        self.assertTrue(employee.user.must_change_password)
