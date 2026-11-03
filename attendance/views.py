from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from core.company import get_company
from core.crud import CrudCreateView, CrudDeleteView, CrudListView, CrudUpdateView
from core.exports import export_response
from core.middleware import get_client_ip
from core.permissions import EmployeeRequiredMixin, HRRequiredMixin, is_hr_or_manager
from core.utils import MONTHS_FR, month_bounds, safe_next
from employees.models import Employee
from leaves.models import LeaveRequest
from leaves.services import holidays_between
from organization.models import Department
from payroll.models import PayrollPeriod

from .forms import AttendanceForm, OvertimeForm, OvertimeTypeForm
from .models import Attendance, OvertimeEntry, OvertimeType


def _team_queryset(user):
    employees = Employee.objects.active().select_related('department', 'position')
    if user.is_hr:
        return employees
    return employees.filter(manager=user.employee_profile)


class MyAttendanceView(EmployeeRequiredMixin, TemplateView):
    template_name = 'attendance/my_attendance.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        first, last = month_bounds(today.year, today.month)
        records = list(self.employee.attendances.filter(date__range=(first, last)).order_by('-date'))
        counts = Counter(r.status for r in records)
        hours = sum((r.worked_hours or Decimal(0)) for r in records)
        context.update({
            'today_record': next((r for r in records if r.date == today), None),
            'records': records,
            'month_label': f'{MONTHS_FR[today.month - 1].capitalize()} {today.year}',
            'stats': {
                'present': counts[Attendance.Status.PRESENT] + counts[Attendance.Status.LATE]
                + counts[Attendance.Status.REMOTE] + counts[Attendance.Status.HALF_DAY],
                'late': counts[Attendance.Status.LATE],
                'absent': counts[Attendance.Status.ABSENT],
                'hours': hours,
            },
            'company': get_company(),
            'overtime': self.employee.overtime_entries.filter(date__range=(first, last)).select_related(
                'overtime_type'),
        })
        return context


@login_required
@require_POST
def punch(request):
    employee = request.user.employee_profile
    if employee is None:
        messages.error(request, "Aucune fiche employé n'est liée à votre compte.")
        return redirect('core:dashboard')
    now = timezone.localtime()
    record, created = Attendance.objects.get_or_create(
        employee=employee, date=now.date(),
        defaults={'source': Attendance.Source.SELF, 'ip_address': get_client_ip(request)},
    )
    action = request.POST.get('action')
    current_time = now.time().replace(second=0, microsecond=0)
    if action == 'in':
        if record.check_in:
            messages.info(request, f'Arrivée déjà pointée à {record.check_in:%H:%M}.')
        else:
            record.check_in = current_time
            record.status = Attendance.status_for_arrival(current_time, get_company())
            record.source = Attendance.Source.SELF
            record.save()
            if record.status == Attendance.Status.LATE:
                messages.warning(request, f'Arrivée pointée à {current_time:%H:%M} (retard).')
            else:
                messages.success(request, f'Arrivée pointée à {current_time:%H:%M}. Bonne journée !')
    elif action == 'out':
        if not record.check_in:
            messages.error(request, "Pointez d'abord votre arrivée.")
        else:
            record.check_out = current_time
            record.save()
            messages.success(request, f'Départ pointé à {current_time:%H:%M}. À bientôt !')
    else:
        messages.error(request, 'Action de pointage inconnue.')
    return redirect(safe_next(request, reverse('attendance:mine')))


class RegisterView(LoginRequiredMixin, TemplateView):
    """Registre journalier des présences."""

    template_name = 'attendance/register.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not is_hr_or_manager(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            day = date.fromisoformat(self.request.GET.get('date', ''))
        except ValueError:
            day = timezone.localdate()
        employees = _team_queryset(self.request.user)
        department = self.request.GET.get('departement')
        if department:
            employees = employees.filter(department_id=department)
        records = {a.employee_id: a for a in Attendance.objects.filter(date=day, employee__in=employees)}
        on_leave = {lr.employee_id: lr for lr in LeaveRequest.objects.filter(
            status=LeaveRequest.Status.APPROVED, start_date__lte=day, end_date__gte=day, employee__in=employees
        ).select_related('leave_type')}
        is_working_day = day.weekday() in get_company().working_days_list and day not in holidays_between(day, day)
        rows = [{'employee': e, 'record': records.get(e.pk), 'leave': on_leave.get(e.pk)} for e in employees]
        counts = Counter(r['record'].status for r in rows if r['record'])
        context.update({
            'day': day, 'prev_day': day - timedelta(days=1), 'next_day': day + timedelta(days=1),
            'rows': rows, 'is_working_day': is_working_day,
            'summary': {
                'total': len(rows),
                'present': counts[Attendance.Status.PRESENT] + counts[Attendance.Status.REMOTE]
                + counts[Attendance.Status.HALF_DAY],
                'late': counts[Attendance.Status.LATE],
                'absent': counts[Attendance.Status.ABSENT],
                'on_leave': len(on_leave),
                'missing': sum(1 for r in rows if not r['record'] and not r['leave']),
            },
            'departments': Department.objects.filter(is_active=True),
            'department': department or '',
            'can_edit': self.request.user.is_hr,
        })
        return context


class MonthlyReportView(LoginRequiredMixin, TemplateView):
    template_name = 'attendance/report.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not is_hr_or_manager(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_period(self):
        today = timezone.localdate()
        try:
            year = int(self.request.GET.get('annee', today.year))
            month = int(self.request.GET.get('mois', today.month))
            date(year, month, 1)
        except ValueError:
            year, month = today.year, today.month
        return year, month

    def build_rows(self, year, month):
        first, last = month_bounds(year, month)
        today = timezone.localdate()
        employees = list(_team_queryset(self.request.user))
        records = defaultdict(list)
        for record in Attendance.objects.filter(date__range=(first, last), employee__in=employees):
            records[record.employee_id].append(record)
        leave_days = defaultdict(int)
        holidays = holidays_between(first, last)
        working = set(get_company().working_days_list)
        for leave in LeaveRequest.objects.filter(status=LeaveRequest.Status.APPROVED, start_date__lte=last,
                                                 end_date__gte=first, employee__in=employees):
            current = max(leave.start_date, first)
            while current <= min(leave.end_date, last):
                if current.weekday() in working and current not in holidays:
                    leave_days[leave.employee_id] += 1
                current += timedelta(days=1)
        expected = 0
        current = first
        while current <= min(last, today):
            if current.weekday() in working and current not in holidays:
                expected += 1
            current += timedelta(days=1)
        rows = []
        for employee in employees:
            items = records.get(employee.pk, [])
            counts = Counter(r.status for r in items)
            worked = counts[Attendance.Status.PRESENT] + counts[Attendance.Status.LATE] \
                + counts[Attendance.Status.REMOTE] + counts[Attendance.Status.HALF_DAY]
            rows.append({
                'employee': employee,
                'worked': worked,
                'late': counts[Attendance.Status.LATE],
                'remote': counts[Attendance.Status.REMOTE],
                'absent': counts[Attendance.Status.ABSENT],
                'leave': leave_days[employee.pk],
                'hours': sum((r.worked_hours or Decimal(0)) for r in items),
                'rate': round(worked * 100 / max(expected - leave_days[employee.pk], 1)) if expected else 0,
            })
        return rows, expected

    def get(self, request, *args, **kwargs):
        year, month = self.get_period()
        if request.GET.get('export') in ('xlsx', 'csv'):
            rows, _expected = self.build_rows(year, month)
            data = [[r['employee'].employee_id, r['employee'].full_name, r['employee'].department,
                     r['worked'], r['late'], r['remote'], r['absent'], r['leave'], r['hours'], r['rate']]
                    for r in rows]
            return export_response(f'presences_{year}_{month:02d}',
                                   ['Matricule', 'Employé', 'Département', 'Jours travaillés', 'Retards',
                                    'Télétravail', 'Absences', 'Jours de congé', 'Heures', 'Taux (%)'],
                                   data, request.GET['export'], sheet_title='Présences')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year, month = self.get_period()
        rows, expected = self.build_rows(year, month)
        context.update({
            'rows': rows, 'expected': expected, 'year': year, 'month': month,
            'month_label': f'{MONTHS_FR[month - 1].capitalize()} {year}',
            'months': [(i + 1, m.capitalize()) for i, m in enumerate(MONTHS_FR)],
            'years': range(timezone.localdate().year - 2, timezone.localdate().year + 1),
        })
        return context


class AttendanceConfig(HRRequiredMixin):
    model = Attendance
    form_class = AttendanceForm
    title = 'Présences'
    list_url_name = 'attendance:register'

    def get_success_url(self):
        return f"{reverse('attendance:register')}?date={self.object.date:%Y-%m-%d}"


class AttendanceCreateView(AttendanceConfig, CrudCreateView):
    form_title = 'Saisir une présence'

    def get_initial(self):
        initial = {'date': self.request.GET.get('date') or timezone.localdate(),
                   'check_in': get_company().work_start, 'check_out': get_company().work_end}
        if self.request.GET.get('employe'):
            initial['employee'] = self.request.GET['employe']
        if self.request.GET.get('statut'):
            initial['status'] = self.request.GET['statut']
            if initial['status'] == Attendance.Status.ABSENT:
                initial['check_in'] = initial['check_out'] = None
        return initial


class AttendanceUpdateView(AttendanceConfig, CrudUpdateView):
    pass


class AttendanceDeleteView(AttendanceConfig, CrudDeleteView):
    pass


# ---------------------------------------------------------------------------
# Heures supplémentaires
# ---------------------------------------------------------------------------

def _can_manage_overtime(user, employee):
    return user.is_hr or employee.is_managed_by(user)


def _payroll_locked(day):
    return PayrollPeriod.objects.filter(year=day.year, month=day.month).exclude(
        status=PayrollPeriod.Status.DRAFT).exists()


class OvertimeListView(LoginRequiredMixin, CrudListView):
    model = OvertimeEntry
    title = 'Heures supplémentaires'
    icon = 'bi-alarm'
    list_url_name = 'attendance:overtime_list'
    create_url_name = 'attendance:overtime_create'
    update_url_name = 'attendance:overtime_update'
    delete_url_name = 'attendance:overtime_delete'
    columns = [('Date', 'date'), ('Employé', 'employee'), ('Type', 'overtime_type'), ('Heures', 'hours'),
               ('Motif', 'note'), ('Saisi par', 'created_by')]
    search_fields = ['employee__first_name', 'employee__last_name', 'note']
    filters = [('overtime_type', 'Type', lambda: OvertimeType.objects.values_list('pk', 'name'))]
    export_columns = [('Date', 'date'), ('Matricule', 'employee.employee_id'), ('Employé', 'employee'),
                      ('Type', 'overtime_type.name'), ('Majoration %', 'overtime_type.increase_rate'),
                      ('Heures', 'hours'), ('Motif', 'note')]
    export_filename = 'heures_supplementaires'
    subtitle = 'Intégrées automatiquement au bulletin de paie du mois concerné.'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not is_hr_or_manager(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset().select_related('employee', 'overtime_type', 'created_by')
        if not self.request.user.is_hr:
            queryset = queryset.filter(employee__manager=self.request.user.employee_profile)
        return queryset


class OvertimeFormMixin(LoginRequiredMixin):
    model = OvertimeEntry
    form_class = OvertimeForm
    title = 'Heures supplémentaires'
    list_url_name = 'attendance:overtime_list'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class OvertimeCreateView(OvertimeFormMixin, CrudCreateView):
    form_title = 'Saisir des heures supplémentaires'
    success_message = 'Heures supplémentaires enregistrées.'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not is_hr_or_manager(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return {'date': timezone.localdate(), 'employee': self.request.GET.get('employe')}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class OvertimeOwnedMixin(OvertimeFormMixin):
    def get_object(self, queryset=None):
        entry = super().get_object(queryset)
        if not _can_manage_overtime(self.request.user, entry.employee):
            raise PermissionDenied
        return entry


class OvertimeUpdateView(OvertimeOwnedMixin, CrudUpdateView):
    pass


class OvertimeDeleteView(OvertimeOwnedMixin, CrudDeleteView):
    def form_valid(self, form):
        if _payroll_locked(self.object.date):
            messages.error(self.request, 'La paie de ce mois est validée : suppression impossible.')
            return redirect(self.get_success_url())
        return super().form_valid(form)


class OvertimeTypeConfig(HRRequiredMixin):
    model = OvertimeType
    form_class = OvertimeTypeForm
    title = "Types d'heures supplémentaires"
    icon = 'bi-percent'
    list_url_name = 'attendance:overtime_type_list'
    create_url_name = 'attendance:overtime_type_create'
    update_url_name = 'attendance:overtime_type_update'
    delete_url_name = 'attendance:overtime_type_delete'


class OvertimeTypeListView(OvertimeTypeConfig, CrudListView):
    columns = [('Libellé', 'name'), ('Code', 'code'), ('Majoration %', 'increase_rate'),
               ('Actif', 'is_active', 'bool')]
    subtitle = 'Taux de majoration à faire valider selon le Code du travail et votre convention collective.'


class OvertimeTypeCreateView(OvertimeTypeConfig, CrudCreateView):
    form_title = "Nouveau type d'heures supplémentaires"


class OvertimeTypeUpdateView(OvertimeTypeConfig, CrudUpdateView):
    pass


class OvertimeTypeDeleteView(OvertimeTypeConfig, CrudDeleteView):
    pass
