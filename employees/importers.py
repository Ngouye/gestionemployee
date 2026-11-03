"""Import d'employés depuis un fichier Excel ou CSV."""
import csv
import io
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from openpyxl import load_workbook

from organization.models import Department, Position

from .models import Contract, Employee

COLUMNS = ['matricule', 'prenom', 'nom', 'email', 'telephone', 'genre', 'date_naissance',
           'departement', 'poste', 'date_embauche', 'type_contrat', 'salaire_base']
REQUIRED = ['prenom', 'nom', 'email', 'date_embauche']
EXAMPLE_ROW = ['', 'Awa', 'Ndiaye', 'awa.ndiaye@entreprise.sn', '+221 77 000 00 00', 'F', '15/03/1992',
               'Finance', 'Comptable', '01/02/2024', 'CDI', 450000]


def _normalize(header):
    text = unicodedata.normalize('NFKD', str(header or '')).encode('ascii', 'ignore').decode()
    return text.strip().lower().replace(' ', '_').replace('-', '_')


def _parse_date(value):
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f'date invalide « {text} » (format attendu JJ/MM/AAAA)')


def _parse_decimal(value):
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value).replace(' ', '').replace(' ', '').replace(',', '.'))
    except InvalidOperation:
        raise ValueError(f'montant invalide « {value} »')


def read_rows(uploaded):
    name = uploaded.name.lower()
    if name.endswith('.xlsx'):
        workbook = load_workbook(uploaded, read_only=True, data_only=True)
        rows = list(workbook.active.iter_rows(values_only=True))
    else:
        text = uploaded.read().decode('utf-8-sig', errors='replace')
        try:
            dialect = csv.Sniffer().sniff(text[:2048], delimiters=';,\t')
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.reader(io.StringIO(text), dialect))
    if not rows:
        return []
    headers = [_normalize(h) for h in rows[0]]
    result = []
    for values in rows[1:]:
        if not any(v not in (None, '') for v in values):
            continue
        result.append({headers[i]: values[i] for i in range(min(len(headers), len(values)))})
    return result


def import_employees(uploaded):
    """Importe les lignes valides. Renvoie (nombre_créés, [(ligne, message), ...])."""
    created, errors = 0, []
    contract_types = {value for value, _ in Contract.Type.choices}
    for line, row in enumerate(read_rows(uploaded), start=2):
        try:
            missing = [col for col in REQUIRED if not str(row.get(col) or '').strip()]
            if missing:
                raise ValueError('colonnes obligatoires manquantes : ' + ', '.join(missing))
            email = str(row['email']).strip().lower()
            try:
                validate_email(email)
            except ValidationError:
                raise ValueError(f'e-mail invalide « {email} »')
            if Employee.objects.filter(email=email).exists():
                raise ValueError(f'un employé avec l’e-mail {email} existe déjà')
            matricule = str(row.get('matricule') or '').strip()
            if matricule and Employee.objects.filter(employee_id=matricule).exists():
                raise ValueError(f'le matricule {matricule} existe déjà')
            hire_date = _parse_date(row.get('date_embauche'))
            salary = _parse_decimal(row.get('salaire_base'))
            contract_type = str(row.get('type_contrat') or 'CDI').strip().upper()
            if contract_type not in contract_types:
                raise ValueError(f'type de contrat inconnu « {contract_type} »')
            gender = str(row.get('genre') or '').strip().upper()[:1]

            with transaction.atomic():
                department = None
                if row.get('departement'):
                    department, _ = Department.objects.get_or_create(name=str(row['departement']).strip())
                position = None
                if row.get('poste'):
                    position, _ = Position.objects.get_or_create(
                        title=str(row['poste']).strip(), department=department)
                employee = Employee.objects.create(
                    employee_id=matricule,
                    first_name=str(row['prenom']).strip(),
                    last_name=str(row['nom']).strip(),
                    email=email,
                    phone=str(row.get('telephone') or '').strip(),
                    gender=gender if gender in ('M', 'F') else '',
                    date_of_birth=_parse_date(row.get('date_naissance')),
                    department=department,
                    position=position,
                    hire_date=hire_date,
                )
                if salary is not None:
                    Contract.objects.create(
                        employee=employee, contract_type=contract_type, position=position,
                        start_date=hire_date, base_salary=salary,
                    )
            created += 1
        except ValueError as exc:
            errors.append((line, str(exc)))
    return created, errors
