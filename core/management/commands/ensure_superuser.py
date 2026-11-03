import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ('Crée le compte administrateur à partir de DJANGO_SUPERUSER_EMAIL et DJANGO_SUPERUSER_PASSWORD '
            "s'il n'existe pas encore (sans jamais modifier un compte existant).")

    def handle(self, *args, **options):
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '').strip().lower()
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
        if not email or not password:
            self.stdout.write('DJANGO_SUPERUSER_EMAIL / DJANGO_SUPERUSER_PASSWORD non définis : étape ignorée.')
            return
        user_model = get_user_model()
        if user_model.objects.filter(email__iexact=email).exists():
            self.stdout.write(f'Le compte administrateur {email} existe déjà.')
            return
        user_model.objects.create_superuser(email=email, password=password, first_name='Administrateur')
        self.stdout.write(self.style.SUCCESS(f'Compte administrateur {email} créé.'))
