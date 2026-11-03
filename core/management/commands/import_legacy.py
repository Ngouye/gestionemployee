"""Reprise des employés de l'ancienne version de l'application (SQLite)."""
import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from employees.models import Contract, Employee
from organization.models import Position


class Command(BaseCommand):
    help = "Importe les employés de l'ancienne base SQLite (legacy/db_ancien.sqlite3 par défaut)."

    def add_arguments(self, parser):
        parser.add_argument('path', nargs='?', default=str(settings.BASE_DIR / 'legacy' / 'db_ancien.sqlite3'))

    def handle(self, *args, **options):
        path = Path(options['path'])
        if not path.exists():
            raise CommandError(f'Fichier introuvable : {path}')
        connection = sqlite3.connect(f'file:{path.as_posix()}?mode=ro', uri=True)
        columns = {row[1] for row in connection.execute('PRAGMA table_info(employees_employee)')}
        if not columns:
            raise CommandError("Aucune table « employees_employee » dans l'ancienne base.")
        wanted = ['name', 'email', 'position', 'salary', 'hire_date', 'phone_number', 'address']
        select = ', '.join(c if c in columns else 'NULL' for c in wanted)
        created = skipped = 0
        with transaction.atomic():
            for name, email, position, salary, hire_date, phone, address in connection.execute(
                    f'SELECT {select} FROM employees_employee'):
                if not email or Employee.objects.filter(email__iexact=email).exists():
                    skipped += 1
                    continue
                parts = (name or '').split()
                first_name = parts[0] if parts else 'Inconnu'
                last_name = ' '.join(parts[1:]) or '—'
                position_obj = None
                if position:
                    position_obj, _ = Position.objects.get_or_create(title=position.strip().capitalize(),
                                                                     department=None)
                hired = date.fromisoformat(hire_date) if hire_date else date.today()
                employee = Employee.objects.create(
                    first_name=first_name.capitalize(), last_name=last_name.upper(), email=email.lower(),
                    phone=phone or '', address=address or '', position=position_obj, hire_date=hired,
                )
                if salary is not None:
                    Contract.objects.create(employee=employee, position=position_obj, start_date=hired,
                                            base_salary=Decimal(str(salary)).quantize(Decimal('1')))
                created += 1
        connection.close()
        self.stdout.write(self.style.SUCCESS(f'{created} employé(s) importé(s), {skipped} ignoré(s) (déjà présents).'))
