from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

PASSWORD = 'Demo2026!'


class DemoDataTestCase(TestCase):
    """Charge le jeu de démonstration une seule fois par classe de tests."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo', password=PASSWORD, stdout=StringIO())
        user_model = get_user_model()
        cls.admin = user_model.objects.get(email='direction@demo.sn')
        cls.hr = user_model.objects.get(email='rh@demo.sn')
        cls.manager = user_model.objects.get(email='manager@demo.sn')
        cls.employee_user = user_model.objects.get(email='employe@demo.sn')

    def login(self, user):
        self.client.force_login(user)
