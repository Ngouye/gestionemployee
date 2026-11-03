import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = 'Attend que la base de données accepte les connexions.'

    def add_arguments(self, parser):
        parser.add_argument('--timeout', type=int, default=60)

    def handle(self, *args, **options):
        deadline = time.monotonic() + options['timeout']
        while True:
            try:
                connections['default'].ensure_connection()
            except OperationalError:
                if time.monotonic() > deadline:
                    raise CommandError('La base de données ne répond pas.')
                self.stdout.write('Base de données indisponible, nouvelle tentative dans 2 s…')
                time.sleep(2)
            else:
                self.stdout.write(self.style.SUCCESS('Base de données disponible.'))
                return
