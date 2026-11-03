import calendar
from collections import defaultdict
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, TemplateView

from core.company import get_company
from core.crud import CrudCreateView, CrudDeleteView, CrudListView, CrudUpdateView
from core.files import serve_file
from core.models import Notification
from core.permissions import EmployeeRequiredMixin, HRRequiredMixin, is_hr, role_required
from core.services import notify
from core.utils import MONTHS_FR, safe_next
from employees.models import Employee
from employees.access import can_view_employee
from organization.models import Department

from . import services
from .forms import HRLeaveForm, LeaveBalanceForm, LeaveDecisionForm, LeaveRequestForm, LeaveTypeForm, PublicHolidayForm
from .models import LeaveBalance, LeaveRequest, LeaveType, PublicHoliday


# ---------------------------------------------------------------------------
# Espace employé
# ---------------------------------------------------------------------------

class MyLeavesView(EmployeeRequiredMixin, TemplateView):
    template_name = 'leaves/my_leaves.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        try:
            year = int(self.request.GET.get('annee', today.year))
        except ValueError:
            year = today.year
        context.update({
            'year': year,
            'years': range(today.year - 2, today.year + 2),
            'balances': services.balances_for(self.employee, year),
            'requests': self.employee.leave_requests.filter(start_date__year=year).select_related('leave_type'),
            'upcoming_holidays': sorted(
                ((d, h) for h in PublicHoliday.objects.all()
                 for d in [h.date.replace(year=today.year) if h.is_recurring else h.date]
                 if today <= d <= today + timedelta(days=120)),
                key=lambda item: item[0],
            )[:6],
        })
        return context


class LeaveRequestCreateView(EmployeeRequiredMixin, CreateView):
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = 'leaves/leave_form.html'
    success_url = reverse_lazy('leaves:my_leaves')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['employee'] = self.employee
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        for key in ('start_date', 'end_date'):
            if self.request.GET.get(key):
                initial[key] = self.request.GET[key]
        return initial

    def form_valid(self, form):
        form.instance.employee = self.employee
        response = super().form_valid(form)
        services.notify_new_request(self.object, actor=self.request.user)
        messages.success(self.request, 'Votre demande a été envoyée pour validation.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['balances'] = services.balances_for(self.employee, timezone.localdate().year)
        context['form_title'] = 'Nouvelle demande de congé'
        return context


class LeaveRequestDetailView(LoginRequiredMixin, DetailView):
    model = LeaveRequest
    template_name = 'leaves/leave_detail.html'
    context_object_name = 'leave'

    def get_object(self, queryset=None):
        leave = super().get_object(queryset)
        if not can_view_employee(self.request.user, leave.employee):
            raise PermissionDenied
        return leave

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        leave = self.object
        context['can_review'] = leave.can_be_reviewed_by(self.request.user)
        context['can_cancel'] = leave.can_be_cancelled_by(self.request.user)
        if context['can_review']:
            context['remaining'] = (services.remaining_days(leave.employee, leave.leave_type, leave.start_date.year,
                                                            exclude_pk=leave.pk)
                                    if leave.leave_type.tracks_balance else None)
            context['overlapping_team'] = services.on_leave_on(leave.start_date).filter(
                employee__department=leave.employee.department).exclude(employee=leave.employee)
        return context


@login_required
@require_POST
def leave_cancel(request, pk):
    leave = get_object_or_404(LeaveRequest, pk=pk)
    if not leave.can_be_cancelled_by(request.user):
        raise PermissionDenied
    leave.status = LeaveRequest.Status.CANCELLED
    leave.save(update_fields=['status', 'updated_at'])
    messages.success(request, 'La demande a été annulée.')
    if leave.employee.user_id != request.user.pk and leave.employee.user:
        notify(leave.employee.user, 'Demande de congé annulée',
               f'Votre demande du {leave.start_date:%d/%m/%Y} a été annulée par les RH.', leave.get_absolute_url())
    return redirect(safe_next(request, reverse('leaves:my_leaves')))


@login_required
@require_POST
def leave_decide(request, pk):
    leave = get_object_or_404(LeaveRequest.objects.select_related('employee__manager', 'employee__user'), pk=pk)
    if not leave.can_be_reviewed_by(request.user):
        raise PermissionDenied
    form = LeaveDecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, ' '.join(form.non_field_errors()) or 'Décision invalide.')
        return redirect(safe_next(request, leave.get_absolute_url()))
    approved = form.cleaned_data['decision'] == 'approve'
    leave.status = LeaveRequest.Status.APPROVED if approved else LeaveRequest.Status.REJECTED
    leave.reviewed_by = request.user
    leave.reviewed_at = timezone.now()
    leave.review_comment = form.cleaned_data.get('comment', '')
    leave.save()
    verdict = 'approuvée' if approved else 'refusée'
    if leave.employee.user:
        notify(leave.employee.user, f'Demande de congé {verdict}',
               f'{leave.leave_type} du {leave.start_date:%d/%m/%Y} au {leave.end_date:%d/%m/%Y}. '
               f'{leave.review_comment}'.strip(), leave.get_absolute_url(),
               Notification.Level.SUCCESS if approved else Notification.Level.DANGER)
    messages.success(request, f'Demande de {leave.employee} {verdict}.')
    return redirect(safe_next(request, reverse('core:approvals')))


@login_required
def leave_attachment(request, pk):
    leave = get_object_or_404(LeaveRequest, pk=pk)
    if not can_view_employee(request.user, leave.employee):
        raise PermissionDenied
    return serve_file(leave.attachment)


# ---------------------------------------------------------------------------
# Gestion RH
# ---------------------------------------------------------------------------

class LeaveRequestListView(HRRequiredMixin, CrudListView):
    model = LeaveRequest
    title = 'Demandes de congé'
    icon = 'bi-calendar2-week'
    list_url_name = 'leaves:list'
    create_url_name = 'leaves:hr_create'
    detail_url_name = 'leaves:detail'
    columns = [('Employé', 'employee'), ('Type', 'leave_type'), ('Du', 'start_date'), ('Au', 'end_date'),
               ('Jours', 'days', 'days'), ('Statut', 'status', 'badge'), ('Déposée le', 'created_at')]
    search_fields = ['employee__first_name', 'employee__last_name', 'employee__employee_id']
    filters = [
        ('status', 'Statut', LeaveRequest.Status.choices),
        ('leave_type', 'Type', lambda: LeaveType.objects.values_list('pk', 'name')),
        ('employee__department', 'Département', lambda: Department.objects.values_list('pk', 'name')),
    ]
    export_columns = [('Matricule', 'employee.employee_id'), ('Employé', 'employee'),
                      ('Département', 'employee.department'), ('Type', 'leave_type'), ('Du', 'start_date'),
                      ('Au', 'end_date'), ('Jours', 'days'), ('Statut', 'get_status_display'),
                      ('Motif', 'reason'), ('Traitée par', 'reviewed_by'), ('Traitée le', 'reviewed_at')]
    export_filename = 'demandes_conges'

    def get_queryset(self):
        return super().get_queryset().select_related('employee', 'leave_type', 'employee__department')


class HRLeaveCreateView(HRRequiredMixin, CrudCreateView):
    model = LeaveRequest
    form_class = HRLeaveForm
    title = 'Demandes de congé'
    list_url_name = 'leaves:list'
    form_title = 'Saisir une absence pour un employé'
    success_message = 'Absence enregistrée et validée.'

    def form_valid(self, form):
        form.instance.status = LeaveRequest.Status.APPROVED
        form.instance.reviewed_by = self.request.user
        form.instance.reviewed_at = timezone.now()
        response = super().form_valid(form)
        employee = self.object.employee
        if employee.user:
            notify(employee.user, 'Absence enregistrée par les RH',
                   f'{self.object.leave_type} du {self.object.start_date:%d/%m/%Y} au {self.object.end_date:%d/%m/%Y}.',
                   self.object.get_absolute_url())
        return response


class LeaveCalendarView(LoginRequiredMixin, TemplateView):
    template_name = 'leaves/calendar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        try:
            year = int(self.request.GET.get('annee', today.year))
            month = int(self.request.GET.get('mois', today.month))
            first = date(year, month, 1)
        except ValueError:
            year, month, first = today.year, today.month, today.replace(day=1)
        last = date(year, month, calendar.monthrange(year, month)[1])

        leaves = (LeaveRequest.objects.filter(start_date__lte=last, end_date__gte=first,
                                              status__in=[LeaveRequest.Status.APPROVED, LeaveRequest.Status.PENDING])
                  .select_related('employee', 'leave_type'))
        user = self.request.user
        department = self.request.GET.get('departement')
        if not user.is_hr:
            own = user.employee_profile
            scope = Q(employee__user=user)
            if own and own.department_id:
                scope |= Q(employee__department_id=own.department_id, status=LeaveRequest.Status.APPROVED)
            if own:
                scope |= Q(employee__manager=own)
            leaves = leaves.filter(scope)
        elif department:
            leaves = leaves.filter(employee__department_id=department)

        holidays = services.holidays_between(first, last)
        worked = set(get_company().working_days_list)
        by_day = defaultdict(list)
        for leave in leaves:
            current = max(leave.start_date, first)
            while current <= min(leave.end_date, last):
                if current.weekday() in worked and current not in holidays:
                    by_day[current].append(leave)
                current += timedelta(days=1)
        holiday_names = {}
        for holiday in PublicHoliday.objects.all():
            day = holiday.date.replace(year=year) if holiday.is_recurring else holiday.date
            if day in holidays:
                holiday_names[day] = holiday.name

        weeks = []
        for week in calendar.Calendar(firstweekday=0).monthdatescalendar(year, month):
            weeks.append([{'date': d, 'in_month': d.month == month, 'is_today': d == today,
                           'leaves': by_day.get(d, []), 'holiday': holiday_names.get(d),
                           'is_weekend': d.weekday() not in worked} for d in week])
        previous = first - timedelta(days=1)
        following = last + timedelta(days=1)
        context.update({
            'weeks': weeks, 'month_label': f'{MONTHS_FR[month - 1].capitalize()} {year}',
            'prev': {'annee': previous.year, 'mois': previous.month},
            'next': {'annee': following.year, 'mois': following.month},
            'leave_types': LeaveType.objects.filter(is_active=True),
            'departments': Department.objects.filter(is_active=True) if user.is_hr else [],
            'department': department or '',
            'weekdays': ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'],
        })
        return context


class BalanceListView(HRRequiredMixin, TemplateView):
    template_name = 'leaves/balances.html'

    def get_year(self):
        try:
            return int(self.request.GET.get('annee', timezone.localdate().year))
        except ValueError:
            return timezone.localdate().year

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year = self.get_year()
        types = list(LeaveType.objects.filter(is_active=True, tracks_balance=True))
        employees = Employee.objects.active().select_related('department')
        query = self.request.GET.get('q', '').strip()
        if query:
            employees = employees.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query))
        balances = {(b.employee_id, b.leave_type_id): b for b in LeaveBalance.objects.filter(year=year)}
        usage = services.usage_by_employee(year)
        rows = []
        for employee in employees:
            cells = []
            for leave_type in types:
                balance = balances.get((employee.pk, leave_type.pk))
                used = usage[(employee.pk, leave_type.pk)]
                total = balance.total if balance else None
                cells.append({
                    'balance': balance, 'total': total, 'used': used['used'], 'pending': used['pending'],
                    'remaining': (total - used['used'] - used['pending']) if total is not None else None,
                })
            rows.append({'employee': employee, 'cells': cells})
        context.update({'year': year, 'types': types, 'rows': rows, 'q': query,
                        'years': range(timezone.localdate().year - 2, timezone.localdate().year + 2),
                        'missing': sum(1 for r in rows for c in r['cells'] if c['balance'] is None)})
        return context


@role_required(is_hr)
@require_POST
def balance_allocate(request):
    try:
        year = int(request.POST.get('annee'))
    except (TypeError, ValueError):
        year = timezone.localdate().year
    created = services.allocate_year(year)
    messages.success(request, f'{created} solde(s) créé(s) pour {year}.')
    return redirect(f"{reverse('leaves:balances')}?annee={year}")


class LeaveBalanceUpdateView(HRRequiredMixin, CrudUpdateView):
    model = LeaveBalance
    form_class = LeaveBalanceForm
    title = 'Soldes de congés'
    list_url_name = 'leaves:balances'

    def get_success_url(self):
        return f"{reverse('leaves:balances')}?annee={self.object.year}"


class LeaveTypeConfig(HRRequiredMixin):
    model = LeaveType
    title = 'Types de congé'
    icon = 'bi-tags'
    list_url_name = 'leaves:type_list'
    create_url_name = 'leaves:type_create'
    update_url_name = 'leaves:type_update'
    delete_url_name = 'leaves:type_delete'


class LeaveTypeListView(LeaveTypeConfig, CrudListView):
    columns = [('Couleur', 'color', 'color'), ('Nom', 'name'), ('Code', 'code'),
               ('Droit annuel', 'annual_allowance', 'days'), ('Solde suivi', 'tracks_balance', 'bool'),
               ('Rémunéré', 'is_paid', 'bool'), ('Justificatif', 'requires_attachment', 'bool'),
               ('Actif', 'is_active', 'bool')]
    search_fields = ['name', 'code']


class LeaveTypeCreateView(LeaveTypeConfig, CrudCreateView):
    form_class = LeaveTypeForm
    form_title = 'Nouveau type de congé'


class LeaveTypeUpdateView(LeaveTypeConfig, CrudUpdateView):
    form_class = LeaveTypeForm


class LeaveTypeDeleteView(LeaveTypeConfig, CrudDeleteView):
    pass


class HolidayConfig(HRRequiredMixin):
    model = PublicHoliday
    title = 'Jours fériés'
    icon = 'bi-calendar-heart'
    list_url_name = 'leaves:holiday_list'
    create_url_name = 'leaves:holiday_create'
    update_url_name = 'leaves:holiday_update'
    delete_url_name = 'leaves:holiday_delete'


class HolidayListView(HolidayConfig, CrudListView):
    columns = [('Nom', 'name'), ('Date', 'date'), ('Récurrent', 'is_recurring', 'bool')]
    search_fields = ['name']
    subtitle = 'Les jours fériés sont exclus du décompte des jours de congé.'


class HolidayCreateView(HolidayConfig, CrudCreateView):
    form_class = PublicHolidayForm
    form_title = 'Nouveau jour férié'


class HolidayUpdateView(HolidayConfig, CrudUpdateView):
    form_class = PublicHolidayForm


class HolidayDeleteView(HolidayConfig, CrudDeleteView):
    pass
