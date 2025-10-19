import os

from django.core.wsgi import get_wsgi_application

# Assurez-vous que 'employeemanager.settings' pointe vers votre fichier settings.py
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'employeemanager.settings')

# C'est la ligne CRITIQUE qui définit l'objet 'application' que Django recherche
application = get_wsgi_application()