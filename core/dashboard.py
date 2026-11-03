"""Indicateurs du tableau de bord."""
from collections import OrderedDict
from datetime import date, timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from attendance.models import Attendance
from employees.models import Contract, Employee, EmployeeDocument
from leaves.models import LeaveRequest
from organization.models import Department
from payroll.models import PayrollPeriod
from recruitment.models import Application, JobOpening

from .utils import MONTHS_FR


def _months_back(today, count):
    months = []
    year, month = today.year, today.month
    for _ in range(count):
        months.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(months))


def hr_dashboard(today):
    active = Employee.objects.active()
    headcount = active.count()
    first_of_month = today.replace(day=1)
    on_leave_today = LeaveRequest.objects.filter(
        status=LeaveRequest.Status.APPROVED, start_date__lte=today, end_date__gte=today
    ).select_related('employee', 'leave_type')
    attendance_today = Attendance.objects.filter(date=today).exclude(status=Attendance.Status.ABSENT).count()
    last_period = PayrollPeriod.objects.exclude(status=PayrollPeriod.Status.DRAFT).first() \
        or PayrollPeriod.objects.first()
    payroll_total = last_period.payslips.aggregate(
        net=Sum('net_salary'), cost=Sum('gross_salary') + Sum('employer_contributions')) if last_period else {}

    kpis = {
        'headcount': headcount,
        'new_hires': active.filter(hire_date__gte=first_of_month).count(),
        'exits_year': Employee.objects.filter(exit_date__year=today.year).count(),
        'on_leave_today': on_leave_today.count(),
        'present_today': attendance_today,
        'attendance_rate': round(attendance_today * 100 / headcount) if headcount else 0,
        'pending_leaves': LeaveRequest.objects.filter(status=LeaveRequest.Status.PENDING).count(),
        'open_jobs': JobOpening.objects.filter(status=JobOpening.Status.OPEN).count(),
        'new_applications': Application.objects.filter(created_at__gte=timezone.now() - timedelta(days=30)).count(),
        'payroll_period': last_period,
        'payroll_net': payroll_total.get('net'),
        'payroll_cost': payroll_total.get('cost'),
    }

    by_department = list(Department.objects.annotate(
        n=Count('employees', filter=Q(employees__status=Employee.Status.ACTIVE))).filter(n__gt=0)
        .order_by('-n').values_list('name', 'n'))
    unassigned = active.filter(department__isnull=True).count()
    if unassigned:
        by_department.append(('Sans département', unassigned))

    months = _months_back(today, 12)
    hires = OrderedDict(((y, m), 0) for y, m in months)
    start = date(months[0][0], months[0][1], 1)
    for hire_date in Employee.objects.filter(hire_date__gte=start).values_list('hire_date', flat=True):
        key = (hire_date.year, hire_date.month)
        if key in hires:
            hires[key] += 1

    gender = dict(active.order_by().values_list('gender').annotate(n=Count('id')))
    contracts = OrderedDict()
    labels = dict(Contract.Type.choices)
    for code, n in (Contract.objects.filter(status=Contract.Status.ACTIVE, employee__status=Employee.Status.ACTIVE)
                    .values_list('contract_type').annotate(n=Count('id')).order_by('-n')):
        contracts[labels.get(code, code).split(' — ')[0]] = n

    charts = {
        'departments': {'labels': [d[0] for d in by_department], 'values': [d[1] for d in by_department]},
        'hires': {'labels': [f'{MONTHS_FR[m - 1][:3].capitalize()} {str(y)[2:]}' for y, m in hires],
                  'values': list(hires.values())},
        'gender': {'labels': ['Femmes', 'Hommes', 'Non renseigné'],
                   'values': [gender.get('F', 0), gender.get('M', 0), gender.get('', 0)]},
        'contracts': {'labels': list(contracts.keys()), 'values': list(contracts.values())},
    }

    for chart in charts.values():
        chart['rows'] = list(zip(chart['labels'], chart['values']))

    alerts = {
        'contracts_ending': Contract.objects.filter(
            status=Contract.Status.ACTIVE, end_date__gte=today, end_date__lte=today + timedelta(days=30)
        ).select_related('employee').order_by('end_date')[:8],
        'trials_ending': Contract.objects.filter(
            status=Contract.Status.ACTIVE, trial_end_date__gte=today, trial_end_date__lte=today + timedelta(days=15)
        ).select_related('employee').order_by('trial_end_date')[:8],
        'documents_expiring': EmployeeDocument.objects.filter(
            expires_on__gte=today, expires_on__lte=today + timedelta(days=30)
        ).select_related('employee').order_by('expires_on')[:8],
        'birthdays': sorted(active.filter(date_of_birth__month=today.month),
                            key=lambda e: e.date_of_birth.day)[:10],
        'anniversaries': [e for e in active.filter(hire_date__month=today.month, hire_date__year__lt=today.year)][:10],
    }
    return {'kpis': kpis, 'charts': charts, 'alerts': alerts, 'on_leave_today': on_leave_today[:8]}
