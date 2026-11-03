"""Jeu de données de démonstration (entreprise fictive)."""
import random
import unicodedata
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from attendance.models import Attendance, OvertimeEntry, OvertimeType
from core.models import Announcement, AuditLog, CompanySettings, Notification
from employees.models import Contract, Employee
from expenses.models import ExpenseCategory, ExpenseClaim
from leaves.models import LeaveRequest, LeaveType, PublicHoliday
from leaves.services import allocate_year, working_days
from organization.models import Department, Position
from payroll.models import PayrollPeriod, PayrollRule, SalaryItem, TaxBracket
from payroll.services import generate_period
from performance.models import Objective, PerformanceReview, ReviewCycle
from recruitment.models import Application, Interview, JobOpening
from training.models import Training, TrainingParticipant

User = get_user_model()

DEPARTMENTS = [
    ('Direction générale', 'DG', [('Directeur général', 'Cadre supérieur', True, 3500000)]),
    ('Ressources humaines', 'RH', [('Directrice des ressources humaines', 'Cadre', True, 1800000),
                                   ('Chargé(e) RH', 'Agent de maîtrise', False, 650000),
                                   ('Assistant(e) administratif(ve)', 'Employé', False, 350000)]),
    ('Finance et comptabilité', 'FIN', [('Directeur financier', 'Cadre', True, 2000000),
                                        ('Comptable', 'Agent de maîtrise', False, 600000),
                                        ('Contrôleur de gestion', 'Cadre', True, 950000)]),
    ("Systèmes d'information", 'DSI', [('Responsable informatique', 'Cadre', True, 1700000),
                                       ('Développeur full-stack', 'Cadre', True, 900000),
                                       ('Administrateur systèmes et réseaux', 'Agent de maîtrise', False, 700000),
                                       ('Technicien support', 'Employé', False, 400000)]),
    ('Commercial et marketing', 'COM', [('Directeur commercial', 'Cadre', True, 1600000),
                                        ('Chargé(e) de clientèle', 'Employé', False, 420000),
                                        ('Chargé(e) de marketing digital', 'Agent de maîtrise', False, 550000)]),
    ('Opérations', 'OPS', [('Responsable des opérations', 'Cadre', True, 1400000),
                           ('Chef de projet', 'Cadre', True, 1000000),
                           ('Agent logistique', 'Ouvrier', False, 300000)]),
]

MALE = ['Moussa', 'Ibrahima', 'Cheikh', 'Abdoulaye', 'Mamadou', 'Ousmane', 'Modou', 'Pape', 'Serigne',
        'Alioune', 'Babacar', 'Lamine', 'Omar', 'Souleymane']
FEMALE = ['Aminata', 'Fatou', 'Awa', 'Mariama', 'Khady', 'Ndèye', 'Aïssatou', 'Coumba', 'Seynabou',
          'Rokhaya', 'Astou', 'Bineta', 'Mame Diarra', 'Adja']
LAST = ['Diop', 'Ndiaye', 'Fall', 'Sow', 'Ba', 'Diallo', 'Sy', 'Faye', 'Gueye', 'Mbaye', 'Sarr', 'Cissé',
        'Niang', 'Thiam', 'Kane', 'Seck', 'Diouf', 'Sall', 'Camara', 'Touré']

DEMO_ACCOUNTS = [
    # (e-mail, rôle, code département, index du poste dans le département)
    ('direction@demo.sn', User.Role.ADMIN, 'DG', 0),
    ('rh@demo.sn', User.Role.HR, 'RH', 0),
    ('manager@demo.sn', User.Role.MANAGER, 'DSI', 0),
    ('employe@demo.sn', User.Role.EMPLOYEE, 'DSI', 1),
]


def _slug(text):
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()
    return ''.join(c if c.isalnum() else '.' for c in text).strip('.')


def _easter(year):
    """Dimanche de Pâques (algorithme grégorien anonyme)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    day = (h + l_ - 7 * m + 114) % 31 + 1
    return date(year, month, day)


class Command(BaseCommand):
    help = "Charge un jeu de données de démonstration complet (entreprise fictive)."

    def add_arguments(self, parser):
        parser.add_argument('--password', default='Demo2026!',
                            help='Mot de passe des comptes de démonstration (défaut : Demo2026!).')
        parser.add_argument('--force', action='store_true',
                            help='Charger même si des employés existent déjà.')

    def handle(self, *args, **options):
        if Employee.objects.exists() and not options['force']:
            self.stdout.write(self.style.WARNING('Des employés existent déjà : aucune donnée de démonstration ajoutée.'))
            return
        self.rng = random.Random(2026)
        self.today = timezone.localdate()
        with transaction.atomic():
            self.company()
            self.organization()
            self.people(options['password'])
            self.leave_setup()
            self.leave_requests()
            self.attendance()
            self.payroll()
            self.expenses()
            self.recruitment()
            self.performance()
            self.training()
            self.communication()
            AuditLog.objects.all().delete()
            AuditLog.objects.create(action=AuditLog.Action.ACTION, model_name='Système',
                                    object_repr='Chargement des données de démonstration')
        self.stdout.write(self.style.SUCCESS(
            f"Données de démonstration chargées : {Employee.objects.count()} employés.\n"
            f"Comptes (mot de passe « {options['password']} ») :\n"
            + '\n'.join(f'  - {email} ({role.label})' for email, role, _d, _p in DEMO_ACCOUNTS)))

    # ------------------------------------------------------------------ socle
    def company(self):
        company = CompanySettings.load()
        company.name = 'Entreprise Démo'
        company.legal_name = 'Entreprise Démo SARL'
        company.industry = 'Services et conseil'
        company.address = 'Avenue Cheikh Anta Diop'
        company.city, company.country = 'Dakar', 'Sénégal'
        company.phone = '+221 33 000 00 00'
        company.email = 'contact@demo.sn'
        company.tax_number = '000000000 2G3'
        company.registration_number = 'SN-DKR-0000-B-00000'
        company.tax_allowance_rate = Decimal(30)
        company.tax_allowance_cap = Decimal(900000)
        company.save()

    def organization(self):
        self.departments, self.positions = {}, {}
        for name, code, positions in DEPARTMENTS:
            department = Department.objects.create(name=name, code=code)
            self.departments[code] = department
            self.positions[code] = []
            for title, grade, executive, salary in positions:
                self.positions[code].append((Position.objects.create(
                    title=title, department=department, grade=grade, is_executive=executive,
                    min_salary=Decimal(salary) * Decimal('0.8'), max_salary=Decimal(salary) * Decimal('1.4'),
                ), salary))

    def _new_employee(self, code, index, manager=None, email=None, hire_date=None, contract_type='CDI'):
        rng = self.rng
        female = rng.random() < 0.45
        first = rng.choice(FEMALE if female else MALE)
        last = rng.choice(LAST)
        position, salary = self.positions[code][index]
        base_email = email or f'{_slug(first)}.{_slug(last)}@demo.sn'
        candidate, n = base_email, 2
        while Employee.objects.filter(email=candidate).exists():
            local, domain = base_email.split('@')
            candidate, n = f'{local}{n}@{domain}', n + 1
        hire_date = hire_date or self.today - timedelta(days=rng.randint(120, 3200))
        employee = Employee.objects.create(
            first_name=first, last_name=last, gender='F' if female else 'M', email=candidate,
            phone=f'+221 7{rng.choice("05678")} {rng.randint(100, 999)} {rng.randint(10, 99)} {rng.randint(10, 99)}',
            date_of_birth=date(rng.randint(1970, 2001), rng.randint(1, 12), rng.randint(1, 28)),
            place_of_birth=rng.choice(['Dakar', 'Thiès', 'Saint-Louis', 'Kaolack', 'Ziguinchor', 'Touba']),
            marital_status=rng.choice(['SINGLE', 'MARRIED', 'MARRIED']),
            children_count=rng.randint(0, 4), address=f'{rng.randint(1, 250)} rue {rng.randint(1, 60)}',
            city=rng.choice(['Dakar', 'Pikine', 'Guédiawaye', 'Rufisque']),
            department=self.departments[code], position=position, manager=manager, hire_date=hire_date,
            work_location='Siège — Dakar', social_security_number=f'{rng.randint(10**8, 10**9 - 1)}',
            bank_name=rng.choice(['CBAO', 'Ecobank', 'Société Générale Sénégal', 'BICIS', 'Banque Atlantique']),
            bank_account=f'SN{rng.randint(10, 99)} {rng.randint(1000, 9999)} {rng.randint(10**9, 10**10 - 1)}',
            emergency_contact_name=f'{rng.choice(FEMALE + MALE)} {last}',
            emergency_contact_relation=rng.choice(['Conjoint(e)', 'Frère', 'Sœur', 'Parent']),
            emergency_contact_phone=f'+221 77 {rng.randint(100, 999)} {rng.randint(10, 99)} {rng.randint(10, 99)}',
        )
        amount = Decimal(int(salary * rng.uniform(0.9, 1.15) / 5000) * 5000)
        end_date = trial = None
        if contract_type == 'CDD':
            end_date = self.today + timedelta(days=rng.choice([20, 75, 160]))
        elif contract_type == 'STAGE':
            end_date = self.today + timedelta(days=90)
            amount = Decimal(150000)
        if (self.today - hire_date).days < 90:
            trial = hire_date + timedelta(days=90)
        Contract.objects.create(employee=employee, contract_type=contract_type, position=position,
                                start_date=hire_date, end_date=end_date, trial_end_date=trial,
                                base_salary=amount)
        return employee

    def people(self, password):
        accounts = {(code, index): (email, role) for email, role, code, index in DEMO_ACCOUNTS}

        def make(code, index, manager=None, **kwargs):
            email, role = accounts.pop((code, index), (None, None))
            employee = self._new_employee(code, index, manager, email=email, **kwargs)
            if email:
                user = User.objects.create_user(email=email, password=password, first_name=employee.first_name,
                                                last_name=employee.last_name, role=role)
                employee.user = user
                employee.save(update_fields=['user'])
            return employee

        ceo = make('DG', 0, hire_date=date(2016, 1, 4))
        heads = {code: make(code, 0, ceo) for code in ('RH', 'FIN', 'DSI', 'COM', 'OPS')}
        for code, head in heads.items():
            head.department.head = head
            head.department.save(update_fields=['head'])
        ceo.department.head = ceo
        ceo.department.save(update_fields=['head'])

        team = [('RH', 1), ('RH', 2), ('FIN', 1), ('FIN', 1), ('FIN', 2), ('DSI', 1), ('DSI', 1), ('DSI', 2),
                ('DSI', 3), ('COM', 1), ('COM', 1), ('COM', 2), ('OPS', 1), ('OPS', 2), ('OPS', 2)]
        self.employees = [ceo, *heads.values()]
        for i, (code, index) in enumerate(team):
            contract_type = 'CDD' if i in (4, 11) else 'CDI'
            hire = self.today - timedelta(days=40) if i == 8 else None
            self.employees.append(make(code, index, heads[code], contract_type=contract_type, hire_date=hire))
        # Une stagiaire et un ancien salarié
        self.employees.append(self._new_employee('COM', 2, heads['COM'], contract_type='STAGE',
                                                 hire_date=self.today - timedelta(days=30)))
        former = self._new_employee('OPS', 2, heads['OPS'], hire_date=date(2019, 3, 1))
        former.status = Employee.Status.TERMINATED
        former.exit_date = self.today - timedelta(days=200)
        former.exit_reason = 'Démission'
        former.save()
        former.contracts.update(status=Contract.Status.ENDED, end_date=former.exit_date)
        self.demo_users = {email: User.objects.get(email=email) for email, *_ in DEMO_ACCOUNTS}
        hr_employee = self.demo_users['rh@demo.sn'].employee
        company = CompanySettings.load()
        company.hr_signatory_name = hr_employee.full_name
        company.hr_signatory_title = 'Directrice des ressources humaines' if hr_employee.gender == 'F' \
            else 'Directeur des ressources humaines'
        company.save()

    # ----------------------------------------------------------------- congés
    def leave_setup(self):
        self.leave_types = {
            'CA': LeaveType.objects.create(name='Congé annuel', code='CA', color='#4f46e5', annual_allowance=24,
                                           max_carry_over=12,
                                           description='2 jours ouvrables par mois de service (à adapter).'),
            'PE': LeaveType.objects.create(name='Permission exceptionnelle', code='PE', color='#f59e0b',
                                           annual_allowance=10,
                                           description='Mariage, naissance, décès d’un proche…'),
            'MAL': LeaveType.objects.create(name='Congé maladie', code='MAL', color='#ef4444', tracks_balance=False,
                                            requires_attachment=True),
            'MAT': LeaveType.objects.create(name='Congé maternité', code='MAT', color='#ec4899',
                                            tracks_balance=False, description='14 semaines.'),
            'CSS': LeaveType.objects.create(name='Congé sans solde', code='CSS', color='#64748b',
                                            tracks_balance=False, is_paid=False),
        }
        for name, month, day in [("Jour de l'An", 1, 1), ("Fête de l'Indépendance", 4, 4), ('Fête du Travail', 5, 1),
                                 ('Assomption', 8, 15), ('Toussaint', 11, 1), ('Noël', 12, 25)]:
            PublicHoliday.objects.create(name=name, date=date(2000, month, day), is_recurring=True)
        for year in (self.today.year, self.today.year + 1):
            easter = _easter(year)
            PublicHoliday.objects.create(name='Lundi de Pâques', date=easter + timedelta(days=1))
            PublicHoliday.objects.create(name='Ascension', date=easter + timedelta(days=39))
            PublicHoliday.objects.create(name='Lundi de Pentecôte', date=easter + timedelta(days=50))
        allocate_year(self.today.year - 1)
        allocate_year(self.today.year)

    def _leave(self, employee, code, start, days, status, reviewer=None, reason=''):
        end = start
        while working_days(start, end) < days:
            end += timedelta(days=1)
        leave = LeaveRequest.objects.create(
            employee=employee, leave_type=self.leave_types[code], start_date=start, end_date=end,
            days=working_days(start, end), status=status, reason=reason,
            reviewed_by=reviewer if status != LeaveRequest.Status.PENDING else None,
            reviewed_at=timezone.now() if status != LeaveRequest.Status.PENDING else None,
        )
        return leave

    def leave_requests(self):
        rng, today = self.rng, self.today
        hr = self.demo_users['rh@demo.sn']
        active = [e for e in self.employees if e.status == Employee.Status.ACTIVE]
        for employee in rng.sample(active, 10):
            start = today - timedelta(days=rng.randint(40, 200))
            self._leave(employee, 'CA', start, rng.randint(3, 10), LeaveRequest.Status.APPROVED, hr,
                        'Congés annuels')
        for employee in rng.sample(active, 3):
            self._leave(employee, 'CA', today - timedelta(days=1), rng.randint(3, 6), LeaveRequest.Status.APPROVED,
                        hr, 'Vacances en famille')
        employe = Employee.objects.get(email='employe@demo.sn')
        self._leave(employe, 'CA', today + timedelta(days=21), 5, LeaveRequest.Status.PENDING,
                    reason='Voyage à Saint-Louis')
        for employee in rng.sample(active, 3):
            if employee.pk == employe.pk:
                continue
            self._leave(employee, rng.choice(['CA', 'PE']), today + timedelta(days=rng.randint(7, 40)),
                        rng.randint(1, 5), LeaveRequest.Status.PENDING, reason='Raisons personnelles')
        self._leave(rng.choice(active), 'CA', today + timedelta(days=10), 4, LeaveRequest.Status.REJECTED, hr,
                    'Pont')
        self._leave(rng.choice(active), 'MAL', today - timedelta(days=15), 2, LeaveRequest.Status.APPROVED, hr,
                    'Arrêt maladie')

    # -------------------------------------------------------------- présences
    def attendance(self):
        rng, today = self.rng, self.today
        company = CompanySettings.load()
        skip_today = {e.user_id for e in self.employees if e.user_id}
        leaves = list(LeaveRequest.objects.filter(status=LeaveRequest.Status.APPROVED))
        records = []
        day = today - timedelta(days=30)
        while day <= today:
            if day.weekday() in company.working_days_list:
                for employee in self.employees:
                    if employee.status != Employee.Status.ACTIVE or employee.hire_date > day:
                        continue
                    if day == today and employee.user_id in skip_today:
                        continue
                    if any(lv.employee_id == employee.pk and lv.start_date <= day <= lv.end_date for lv in leaves):
                        continue
                    roll = rng.random()
                    if roll < 0.03:
                        records.append(Attendance(employee=employee, date=day, status=Attendance.Status.ABSENT,
                                                  note='Absence non justifiée'))
                        continue
                    minutes = rng.randint(-25, 12) if roll > 0.15 else rng.randint(16, 70)
                    check_in = (datetime.combine(day, company.work_start) + timedelta(minutes=minutes)).time()
                    check_out = None
                    if day < today:
                        check_out = (datetime.combine(day, company.work_end)
                                     + timedelta(minutes=rng.randint(-20, 60))).time()
                    status = Attendance.status_for_arrival(check_in, company)
                    if roll > 0.93:
                        status = Attendance.Status.REMOTE
                    records.append(Attendance(employee=employee, date=day, check_in=check_in, check_out=check_out,
                                              status=status, source=Attendance.Source.SELF))
            day += timedelta(days=1)
        Attendance.objects.bulk_create(records)

    # ------------------------------------------------------------------- paie
    def payroll(self):
        rules = [
            ('IPRES_RG', 'IPRES — Régime général', 'ALL', '5.6', '8.4', 432000, True,
             'Retraite, plafond mensuel — taux à valider'),
            ('IPRES_RC', 'IPRES — Régime complémentaire cadres', 'EXECUTIVES', '2.4', '3.6', 1296000, True,
             'Cadres uniquement — taux à valider'),
            ('CSS_PF', 'CSS — Prestations familiales', 'ALL', '0', '7', 63000, True, 'Part patronale'),
            ('CSS_AT', 'CSS — Accidents du travail', 'ALL', '0', '1', 63000, True,
             'Taux selon le risque de l’activité (1, 3 ou 5 %)'),
            ('IPM', 'IPM — Prévoyance maladie', 'ALL', '3', '3', 250000, True, 'Selon la convention de votre IPM'),
            ('CFCE', 'Contribution forfaitaire à la charge de l’employeur', 'ALL', '0', '3', None, False, ''),
        ]
        for order, (code, name, scope, emp, er, ceiling, deductible, notes) in enumerate(rules, start=1):
            PayrollRule.objects.create(code=code, name=name, applies_to=scope, employee_rate=Decimal(emp),
                                       employer_rate=Decimal(er), ceiling=ceiling, is_tax_deductible=deductible,
                                       order=order * 10, notes=notes)
        for low, high, rate in [(0, 630000, 0), (630000, 1500000, 20), (1500000, 4000000, 30),
                                (4000000, 8000000, 35), (8000000, 13500000, 37), (13500000, None, 40)]:
            TaxBracket.objects.create(lower_bound=low, upper_bound=high, rate=rate)

        for employee in self.employees:
            if employee.status != Employee.Status.ACTIVE:
                continue
            SalaryItem.objects.create(employee=employee, label='Indemnité de transport', amount=26000,
                                      is_taxable=False)
            if employee.position and employee.position.is_executive:
                SalaryItem.objects.create(employee=employee, label='Prime de responsabilité',
                                          amount=self.rng.choice([50000, 75000, 100000]))
        SalaryItem.objects.create(employee=self.employees[7], label='Remboursement avance sur salaire',
                                  kind=SalaryItem.Kind.DEDUCTION, amount=50000)
        last = self.today.replace(day=1) - timedelta(days=1)
        SalaryItem.objects.create(employee=self.employees[9], label='Prime exceptionnelle', amount=150000,
                                  is_recurring=False, year=self.today.year, month=self.today.month)

        hr = self.demo_users['rh@demo.sn']
        # Les types par défaut sont créés par la migration attendance.0004.
        types = [OvertimeType.objects.get_or_create(code=code, defaults={'name': name, 'increase_rate': rate})[0]
                 for code, name, rate in [('HS15', 'De la 41e à la 48e heure', 15),
                                          ('HS40', 'Au-delà de la 48e heure', 40),
                                          ('HSN', 'Heures de nuit', 60)]]
        manager = self.demo_users['manager@demo.sn']
        for employee in [e for e in self.employees if e.manager and e.manager.user == manager][:3]:
            for day, hours, overtime_type in [(last.replace(day=12), 3, types[0]), (last.replace(day=19), 2, types[2]),
                                              (self.today.replace(day=min(5, self.today.day)), 4, types[0])]:
                OvertimeEntry.objects.create(employee=employee, date=day, hours=hours, overtime_type=overtime_type,
                                             note='Mise en production', created_by=manager)
        previous = PayrollPeriod.objects.create(year=last.year, month=last.month)
        generate_period(previous)
        previous.status = PayrollPeriod.Status.PAID
        previous.validated_by = hr
        previous.validated_at = timezone.now()
        previous.payment_date = last
        previous.save()
        current = PayrollPeriod.objects.create(year=self.today.year, month=self.today.month)
        generate_period(current)

    # --------------------------------------------------------- notes de frais
    def expenses(self):
        categories = {name: ExpenseCategory.objects.create(name=name, max_amount=limit) for name, limit in [
            ('Transport', 100000), ("Repas d'affaires", 75000), ('Hébergement', 300000),
            ('Fournitures', 150000), ('Téléphone et internet', 50000), ('Formation', None)]}
        rng, hr = self.rng, self.demo_users['rh@demo.sn']
        samples = [('Taxi rendez-vous client', 'Transport', 15000), ('Déjeuner avec un partenaire', "Repas d'affaires",
                   42000), ('Hôtel mission à Thiès', 'Hébergement', 85000), ('Recharge internet mission',
                   'Téléphone et internet', 10000), ('Cartouches imprimante', 'Fournitures', 38000)]
        statuses = [ExpenseClaim.Status.SUBMITTED, ExpenseClaim.Status.APPROVED, ExpenseClaim.Status.PAID,
                    ExpenseClaim.Status.PAID, ExpenseClaim.Status.REJECTED]
        for employee in rng.sample([e for e in self.employees if e.status == Employee.Status.ACTIVE], 8):
            title, category, amount = rng.choice(samples)
            status = rng.choice(statuses)
            ExpenseClaim.objects.create(
                employee=employee, title=title, category=categories[category],
                expense_date=self.today - timedelta(days=rng.randint(2, 40)), amount=amount, status=status,
                reviewed_by=hr if status != ExpenseClaim.Status.SUBMITTED else None,
                reviewed_at=timezone.now() if status != ExpenseClaim.Status.SUBMITTED else None,
                review_comment='Justificatif manquant' if status == ExpenseClaim.Status.REJECTED else '',
                paid_at=self.today - timedelta(days=2) if status == ExpenseClaim.Status.PAID else None,
            )
        ExpenseClaim.objects.create(employee=Employee.objects.get(email='employe@demo.sn'),
                                    title='Taxi — intervention client', category=categories['Transport'],
                                    expense_date=self.today - timedelta(days=3), amount=12000)

    # ------------------------------------------------------------- recrutement
    def recruitment(self):
        rng, hr = self.rng, self.demo_users['rh@demo.sn']
        dsi_position = self.positions['DSI'][1][0]
        jobs = [
            JobOpening.objects.create(
                title='Développeur full-stack (Python / JavaScript)', department=self.departments['DSI'],
                position=dsi_position, contract_type='CDI', openings=2, status=JobOpening.Status.OPEN,
                salary_range='800 000 – 1 100 000 FCFA brut / mois', created_by=hr,
                closing_date=self.today + timedelta(days=30),
                description="Au sein de la DSI, vous concevez et maintenez nos applications métiers.\n"
                            "Vous participez aux choix techniques et aux revues de code.",
                requirements="Bac+3/5 en informatique, 3 ans d'expérience.\nPython/Django, JavaScript, SQL, Git."),
            JobOpening.objects.create(
                title='Comptable confirmé(e)', department=self.departments['FIN'],
                position=self.positions['FIN'][1][0], contract_type='CDI', status=JobOpening.Status.OPEN,
                created_by=hr, closing_date=self.today + timedelta(days=15),
                description='Tenue de la comptabilité générale, déclarations fiscales et sociales, clôtures.',
                requirements='BTS/DSCG, maîtrise du SYSCOHADA révisé, 5 ans d’expérience.'),
            JobOpening.objects.create(
                title='Chargé(e) de clientèle', department=self.departments['COM'],
                position=self.positions['COM'][1][0], contract_type='CDD', status=JobOpening.Status.DRAFT,
                created_by=hr, description='Accueil, suivi et fidélisation du portefeuille clients.'),
        ]
        stages = [Application.Stage.NEW, Application.Stage.NEW, Application.Stage.SCREENING,
                  Application.Stage.SCREENING, Application.Stage.INTERVIEW, Application.Stage.OFFER,
                  Application.Stage.REJECTED]
        manager = self.demo_users['manager@demo.sn']
        for job in jobs[:2]:
            for stage in stages:
                female = rng.random() < 0.5
                first, last = rng.choice(FEMALE if female else MALE), rng.choice(LAST)
                application = Application.objects.create(
                    job=job, first_name=first, last_name=last, email=f'{_slug(first)}.{_slug(last)}@exemple.sn',
                    phone=f'+221 77 {rng.randint(100, 999)} {rng.randint(10, 99)} {rng.randint(10, 99)}',
                    stage=stage, rating=rng.choice([None, 3, 4, 5]),
                    source=rng.choice([s for s, _ in Application.Source.choices]),
                    cover_letter='Madame, Monsieur,\nVotre offre a retenu toute mon attention…')
                if stage in (Application.Stage.INTERVIEW, Application.Stage.OFFER):
                    Interview.objects.create(
                        application=application, interviewer=manager if job == jobs[0] else hr,
                        scheduled_at=timezone.make_aware(datetime.combine(
                            self.today + timedelta(days=rng.randint(1, 6)), time(rng.choice([9, 11, 15]), 0))),
                        mode=rng.choice([Interview.Mode.ONSITE, Interview.Mode.VIDEO]))

    # ------------------------------------------------------------- évaluations
    def performance(self):
        cycle = ReviewCycle.objects.create(
            name=f'Entretiens annuels {self.today.year}', start_date=self.today - timedelta(days=20),
            end_date=self.today + timedelta(days=40), status=ReviewCycle.Status.IN_PROGRESS,
            description='Bilan de l’année écoulée et fixation des objectifs.')
        hr = self.demo_users['rh@demo.sn']
        for i, employee in enumerate(e for e in self.employees if e.status == Employee.Status.ACTIVE):
            reviewer = employee.manager.user if employee.manager and employee.manager.user else hr
            review = PerformanceReview.objects.create(cycle=cycle, employee=employee, reviewer=reviewer)
            if i % 3 == 0 and employee.user_id != reviewer.pk:
                review.status = PerformanceReview.Status.COMPLETED
                review.quality_rating, review.productivity_rating = 4, self.rng.choice([3, 4, 5])
                review.teamwork_rating, review.initiative_rating = self.rng.choice([3, 4, 5]), 4
                review.overall_rating = 4
                review.strengths = 'Rigueur, fiabilité et très bon esprit d’équipe.'
                review.improvements = 'Gagner en autonomie sur la priorisation.'
                review.completed_at = timezone.now()
                review.save()
            for title, progress, status in [('Réduire les délais de traitement de 15 %', 60, 'IN_PROGRESS'),
                                            ('Suivre une formation certifiante', 100, 'ACHIEVED')][: 1 + i % 2]:
                Objective.objects.create(employee=employee, cycle=cycle, title=title, progress=progress,
                                         status=status, due_date=self.today + timedelta(days=120),
                                         created_by=reviewer)

    # --------------------------------------------------------------- formation
    def training(self):
        active = [e for e in self.employees if e.status == Employee.Status.ACTIVE]
        done = Training.objects.create(
            title='Excel avancé et tableaux croisés dynamiques', category='Bureautique', provider='Centre de formation',
            start_date=self.today - timedelta(days=45), end_date=self.today - timedelta(days=44),
            duration_hours=14, cost=750000, status=Training.Status.COMPLETED, is_open_for_requests=False)
        for employee in self.rng.sample(active, 6):
            TrainingParticipant.objects.create(training=done, employee=employee,
                                               status=TrainingParticipant.Status.ATTENDED,
                                               satisfaction=self.rng.choice([4, 5]), feedback='Très utile.')
        upcoming = Training.objects.create(
            title="Management d'équipe", category='Management', provider='Cabinet RH',
            start_date=self.today + timedelta(days=20), end_date=self.today + timedelta(days=22),
            duration_hours=21, capacity=10, cost=1800000, mode=Training.Mode.HYBRID)
        for employee in active[1:6]:
            TrainingParticipant.objects.create(training=upcoming, employee=employee)
        Training.objects.create(
            title='Cybersécurité : les bons réflexes', category='Informatique', trainer='DSI interne',
            start_date=self.today + timedelta(days=35), end_date=self.today + timedelta(days=35),
            duration_hours=3, capacity=30, mode=Training.Mode.ONLINE, location='Visioconférence')

    # ---------------------------------------------------------- communication
    def communication(self):
        author = self.demo_users['rh@demo.sn']
        Announcement.objects.create(
            title='Bienvenue sur votre nouvel espace RH', category=Announcement.Category.GENERAL, is_pinned=True,
            author=author, content='Demandes de congé, bulletins de paie, notes de frais, pointage : tout se fait '
                                   'désormais en ligne. N’hésitez pas à contacter le service RH pour toute question.')
        Announcement.objects.create(
            title='Campagne des entretiens annuels', category=Announcement.Category.EVENT, author=author,
            content='La campagne est ouverte : rédigez votre auto-évaluation avant la fin du mois.')
        Announcement.objects.create(
            title='Fermeture exceptionnelle', category=Announcement.Category.URGENT, author=author,
            content='Les bureaux fermeront à 15 h vendredi pour l’inventaire annuel.',
            expires_at=timezone.now() + timedelta(days=10))
        employe = self.demo_users['employe@demo.sn']
        Notification.objects.create(user=employe, title='Bienvenue !', level=Notification.Level.SUCCESS,
                                    message='Votre espace collaborateur est prêt.', url='/')
