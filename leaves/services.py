from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Q, Sum

from core.company import get_company
from core.models import Notification
from core.services import notify, notify_hr
from employees.models import Employee

from .models import LeaveBalance, LeaveRequest, LeaveType, PublicHoliday


def holidays_between(start, end):
    """Dates fériées (ponctuelles et récurrentes) comprises entre deux dates."""
    dates = set(PublicHoliday.objects.filter(is_recurring=False, date__range=(start, end))
                .values_list('date', flat=True))
    recurring = list(PublicHoliday.objects.filter(is_recurring=True).values_list('date', flat=True))
    for year in range(start.year, end.year + 1):
        for holiday in recurring:
            try:
                candidate = holiday.replace(year=year)
            except ValueError:  # 29 février
                continue
            if start <= candidate <= end:
                dates.add(candidate)
    return dates


def working_days(start, end, half_day=False):
    """Nombre de jours ouvrés (jours travaillés hors fériés) entre deux dates incluses."""
    if not start or not end or end < start:
        return Decimal(0)
    worked = set(get_company().working_days_list)
    holidays = holidays_between(start, end)
    count = 0
    current = start
    while current <= end:
        if current.weekday() in worked and current not in holidays:
            count += 1
        current += timedelta(days=1)
    if half_day and count:
        return Decimal('0.5')
    return Decimal(count)


def get_balance(employee, leave_type, year):
    balance, _ = LeaveBalance.objects.get_or_create(
        employee=employee, leave_type=leave_type, year=year,
        defaults={'allocated': leave_type.annual_allowance},
    )
    return balance


def _consumed(employee, leave_type, year, statuses, exclude_pk=None):
    queryset = LeaveRequest.objects.filter(employee=employee, leave_type=leave_type,
                                           start_date__year=year, status__in=statuses)
    if exclude_pk:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset.aggregate(total=Sum('days'))['total'] or Decimal(0)


def remaining_days(employee, leave_type, year, exclude_pk=None):
    """Solde disponible en tenant compte des demandes approuvées et en attente."""
    balance = get_balance(employee, leave_type, year)
    consumed = _consumed(employee, leave_type, year,
                         [LeaveRequest.Status.APPROVED, LeaveRequest.Status.PENDING], exclude_pk)
    return balance.total - consumed


def balances_for(employee, year):
    """Synthèse des soldes d'un employé pour une année."""
    result = []
    usage = usage_by_employee(year, employee_ids=[employee.pk])
    for leave_type in LeaveType.objects.filter(is_active=True, tracks_balance=True):
        balance = get_balance(employee, leave_type, year)
        used = usage[(employee.pk, leave_type.pk)]['used']
        pending = usage[(employee.pk, leave_type.pk)]['pending']
        result.append({
            'leave_type': leave_type, 'balance': balance, 'total': balance.total,
            'used': used, 'pending': pending, 'remaining': balance.total - used - pending,
        })
    return result


def usage_by_employee(year, employee_ids=None):
    """Jours consommés / en attente par (employé, type) pour une année, en une requête."""
    queryset = LeaveRequest.objects.filter(start_date__year=year)
    if employee_ids is not None:
        queryset = queryset.filter(employee_id__in=employee_ids)
    rows = queryset.values('employee_id', 'leave_type_id').annotate(
        used=Sum('days', filter=Q(status=LeaveRequest.Status.APPROVED)),
        pending=Sum('days', filter=Q(status=LeaveRequest.Status.PENDING)),
    )
    usage = defaultdict(lambda: {'used': Decimal(0), 'pending': Decimal(0)})
    for row in rows:
        usage[(row['employee_id'], row['leave_type_id'])] = {
            'used': row['used'] or Decimal(0), 'pending': row['pending'] or Decimal(0)}
    return usage


def allocate_year(year):
    """Crée les soldes manquants de l'année pour tous les employés actifs (avec report)."""
    created = 0
    types = list(LeaveType.objects.filter(is_active=True, tracks_balance=True))
    employees = list(Employee.objects.active())
    previous_usage = usage_by_employee(year - 1)
    previous = {(b.employee_id, b.leave_type_id): b
                for b in LeaveBalance.objects.filter(year=year - 1)}
    for employee in employees:
        for leave_type in types:
            if LeaveBalance.objects.filter(employee=employee, leave_type=leave_type, year=year).exists():
                continue
            carried = Decimal(0)
            last = previous.get((employee.pk, leave_type.pk))
            if last and leave_type.max_carry_over:
                left = last.total - previous_usage[(employee.pk, leave_type.pk)]['used']
                carried = max(Decimal(0), min(left, leave_type.max_carry_over))
            LeaveBalance.objects.create(employee=employee, leave_type=leave_type, year=year,
                                        allocated=leave_type.annual_allowance, carried_over=carried)
            created += 1
    return created


def overlapping_requests(employee, start, end, exclude_pk=None):
    queryset = LeaveRequest.objects.filter(
        employee=employee, status__in=[LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED],
        start_date__lte=end, end_date__gte=start,
    )
    if exclude_pk:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset


def on_leave_on(day):
    """Demandes approuvées couvrant une date donnée."""
    return LeaveRequest.objects.filter(status=LeaveRequest.Status.APPROVED,
                                       start_date__lte=day, end_date__gte=day)


def notify_new_request(leave, actor=None):
    """Prévient le responsable hiérarchique (ou les RH à défaut) d'une nouvelle demande."""
    employee = leave.employee
    title = f'Nouvelle demande de congé : {employee}'
    body = f'{leave.leave_type} du {leave.start_date:%d/%m/%Y} au {leave.end_date:%d/%m/%Y} ({leave.days} j).'
    manager = employee.manager
    if manager and manager.user:
        notify(manager.user, title, body, leave.get_absolute_url(), Notification.Level.WARNING)
    else:
        notify_hr(title, body, leave.get_absolute_url(), Notification.Level.WARNING, exclude=actor)
