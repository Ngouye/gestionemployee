from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from core.company import get_company
from core.crud import CrudCreateView, CrudDeleteView, CrudListView, CrudUpdateView
from core.exports import export_response
from core.models import AuditLog, Notification
from core.permissions import EmployeeRequiredMixin, HRRequiredMixin, is_admin, is_hr, role_required
from core.services import log_action, notify
from core.utils import format_money
from employees.models import Employee

from . import services
from .forms import PayrollPeriodForm, PayrollRuleForm, SalaryItemForm, TaxBracketForm
from .models import PayrollPeriod, PayrollRule, Payslip, SalaryItem, TaxBracket
from .pdf import render_payslip_pdf


def can_view_payslip(user, payslip):
    if user.is_hr:
        return True
    own = user.employee_profile
    return (own is not None and own.pk == payslip.employee_id
            and payslip.period.status != PayrollPeriod.Status.DRAFT)


# ---------------------------------------------------------------------------
# Périodes de paie
# ---------------------------------------------------------------------------

class PeriodListView(HRRequiredMixin, CrudListView):
    model = PayrollPeriod
    template_name = 'payroll/period_list.html'
    title = 'Périodes de paie'
    icon = 'bi-cash-stack'
    list_url_name = 'payroll:period_list'
    create_url_name = 'payroll:period_create'
    paginate_by = 24

    def get_queryset(self):
        return super().get_queryset().annotate(
            payslip_count=Count('payslips'), total_net=Sum('payslips__net_salary'),
            total_gross=Sum('payslips__gross_salary'), total_employer=Sum('payslips__employer_contributions'))


class PeriodCreateView(HRRequiredMixin, CrudCreateView):
    model = PayrollPeriod
    form_class = PayrollPeriodForm
    title = 'Périodes de paie'
    list_url_name = 'payroll:period_list'
    form_title = 'Nouvelle période de paie'

    def get_success_url(self):
        return self.object.get_absolute_url()


class PeriodDeleteView(HRRequiredMixin, CrudDeleteView):
    model = PayrollPeriod
    title = 'Périodes de paie'
    list_url_name = 'payroll:period_list'

    def get_object(self, queryset=None):
        period = super().get_object(queryset)
        if not period.is_editable:
            raise PermissionDenied('Une période validée ne peut pas être supprimée.')
        return period


class PeriodDetailView(HRRequiredMixin, DetailView):
    model = PayrollPeriod
    template_name = 'payroll/period_detail.html'
    context_object_name = 'period'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        export = request.GET.get('export')
        if export == 'livre':
            return self.export_ledger()
        if export == 'virements':
            return self.export_transfers()
        return self.render_to_response(self.get_context_data(object=self.object))

    def payslips(self):
        return self.object.payslips.select_related('employee').order_by('employee_name')

    def export_ledger(self):
        headers = ['N° bulletin', 'Matricule', 'Employé', 'Poste', 'Département', 'Salaire de base', 'Brut',
                   'Cotisations salariales', 'Impôt sur le revenu', 'Autres retenues', 'Net à payer',
                   'Charges patronales', 'Coût employeur']
        rows = [[p.number, p.employee.employee_id, p.employee_name, p.position_title, p.department_name,
                 p.base_salary, p.gross_salary, p.employee_contributions, p.income_tax, p.other_deductions,
                 p.net_salary, p.employer_contributions, p.employer_cost] for p in self.payslips()]
        return export_response(f'livre_de_paie_{self.object.year}_{self.object.month:02d}', headers, rows,
                               sheet_title='Livre de paie')

    def export_transfers(self):
        headers = ['Matricule', 'Bénéficiaire', 'Mode de paiement', 'Banque', 'Compte', 'Montant net']
        rows = [[p.employee.employee_id, p.employee_name, p.employee.get_payment_method_display(),
                 p.employee.bank_name, p.employee.bank_account, p.net_salary] for p in self.payslips()]
        return export_response(f'ordre_virement_{self.object.year}_{self.object.month:02d}', headers, rows,
                               sheet_title='Virements')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['payslips'] = self.payslips()
        context['totals'] = services.period_totals(self.object)
        context['eligible_count'] = services.eligible_employees(self.object).count()
        context['can_reopen'] = is_admin(self.request.user)
        return context


@role_required(is_hr)
@require_POST
def period_generate(request, pk):
    period = get_object_or_404(PayrollPeriod, pk=pk)
    try:
        created, skipped = services.generate_period(period)
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f'{created} bulletin(s) calculé(s) pour {period.label}.')
        if skipped:
            messages.warning(request, 'Non calculés : ' + ' ; '.join(skipped))
    return redirect(period.get_absolute_url())


@role_required(is_hr)
@require_POST
def period_validate(request, pk):
    period = get_object_or_404(PayrollPeriod, pk=pk)
    if period.status != PayrollPeriod.Status.DRAFT or not period.payslips.exists():
        messages.error(request, 'La période doit être en brouillon et contenir des bulletins.')
        return redirect(period.get_absolute_url())
    period.status = PayrollPeriod.Status.VALIDATED
    period.validated_by = request.user
    period.validated_at = timezone.now()
    period.save()
    log_action(AuditLog.Action.ACTION, period, f'Validation de la paie {period.label}')
    company = get_company()
    for payslip in period.payslips.select_related('employee__user'):
        if payslip.employee.user:
            net = format_money(payslip.net_salary, company.currency_decimals, company.currency)
            notify(payslip.employee.user, f'Bulletin de paie disponible — {period.label}',
                   f'Net à payer : {net}', payslip.get_absolute_url(), Notification.Level.SUCCESS)
    messages.success(request, f'Paie de {period.label} validée. Les bulletins sont visibles par les employés.')
    return redirect(period.get_absolute_url())


@role_required(is_hr)
@require_POST
def period_mark_paid(request, pk):
    period = get_object_or_404(PayrollPeriod, pk=pk)
    if period.status != PayrollPeriod.Status.VALIDATED:
        messages.error(request, 'Seule une période validée peut être marquée comme payée.')
        return redirect(period.get_absolute_url())
    period.status = PayrollPeriod.Status.PAID
    period.payment_date = period.payment_date or timezone.localdate()
    period.save()
    messages.success(request, f'Paie de {period.label} marquée comme payée.')
    return redirect(period.get_absolute_url())


@role_required(is_admin)
@require_POST
def period_reopen(request, pk):
    period = get_object_or_404(PayrollPeriod, pk=pk)
    period.status = PayrollPeriod.Status.DRAFT
    period.validated_at = None
    period.validated_by = None
    period.save()
    log_action(AuditLog.Action.ACTION, period, f'Réouverture de la paie {period.label}')
    messages.warning(request, f'Période {period.label} rouverte en brouillon.')
    return redirect(period.get_absolute_url())


# ---------------------------------------------------------------------------
# Bulletins
# ---------------------------------------------------------------------------

class PayslipDetailView(LoginRequiredMixin, DetailView):
    model = Payslip
    template_name = 'payroll/payslip_detail.html'
    context_object_name = 'payslip'

    def get_queryset(self):
        return Payslip.objects.select_related('period', 'employee').prefetch_related('lines')

    def get_object(self, queryset=None):
        payslip = super().get_object(queryset)
        if not can_view_payslip(self.request.user, payslip):
            raise PermissionDenied
        return payslip


@login_required
def payslip_pdf(request, pk):
    payslip = get_object_or_404(Payslip.objects.select_related('period', 'employee'), pk=pk)
    if not can_view_payslip(request.user, payslip):
        raise PermissionDenied
    response = HttpResponse(render_payslip_pdf(payslip), content_type='application/pdf')
    disposition = 'attachment' if request.GET.get('telecharger') else 'inline'
    response['Content-Disposition'] = f'{disposition}; filename="{payslip.number}.pdf"'
    return response


class MyPayslipsView(EmployeeRequiredMixin, ListView):
    template_name = 'payroll/my_payslips.html'
    context_object_name = 'payslips'
    paginate_by = 24

    def get_queryset(self):
        return (Payslip.objects.filter(employee=self.employee)
                .exclude(period__status=PayrollPeriod.Status.DRAFT).select_related('period'))


# ---------------------------------------------------------------------------
# Paramétrage
# ---------------------------------------------------------------------------

class RuleConfig(HRRequiredMixin):
    model = PayrollRule
    form_class = PayrollRuleForm
    title = 'Cotisations sociales'
    icon = 'bi-percent'
    list_url_name = 'payroll:rule_list'
    create_url_name = 'payroll:rule_create'
    update_url_name = 'payroll:rule_update'
    delete_url_name = 'payroll:rule_delete'


class RuleListView(RuleConfig, CrudListView):
    columns = [('Code', 'code'), ('Libellé', 'name'), ('Assiette', 'get_base_display'),
               ('Salariés concernés', 'get_applies_to_display'),
               ('Taux salarial %', 'employee_rate'), ('Taux patronal %', 'employer_rate'),
               ('Plafond', 'ceiling', 'money'), ('Déductible IR', 'is_tax_deductible', 'bool'),
               ('Active', 'is_active', 'bool')]
    search_fields = ['code', 'name']
    subtitle = 'Taux et plafonds à faire valider par votre expert-comptable.'


class RuleCreateView(RuleConfig, CrudCreateView):
    form_title = 'Nouvelle cotisation'


class RuleUpdateView(RuleConfig, CrudUpdateView):
    pass


class RuleDeleteView(RuleConfig, CrudDeleteView):
    pass


class BracketConfig(HRRequiredMixin):
    model = TaxBracket
    form_class = TaxBracketForm
    title = "Barème de l'impôt sur le revenu"
    icon = 'bi-bar-chart-steps'
    list_url_name = 'payroll:bracket_list'
    create_url_name = 'payroll:bracket_create'
    update_url_name = 'payroll:bracket_update'
    delete_url_name = 'payroll:bracket_delete'


class BracketListView(BracketConfig, CrudListView):
    columns = [('De (annuel)', 'lower_bound', 'money'), ('À (annuel)', 'upper_bound', 'money'),
               ('Taux %', 'rate')]
    subtitle = 'Barème progressif annuel appliqué au revenu imposable annualisé.'


class BracketCreateView(BracketConfig, CrudCreateView):
    form_title = 'Nouvelle tranche'


class BracketUpdateView(BracketConfig, CrudUpdateView):
    pass


class BracketDeleteView(BracketConfig, CrudDeleteView):
    pass


class SalaryItemConfig(HRRequiredMixin):
    model = SalaryItem
    form_class = SalaryItemForm
    title = 'Primes et retenues'
    icon = 'bi-plus-slash-minus'
    list_url_name = 'payroll:item_list'
    create_url_name = 'payroll:item_create'
    update_url_name = 'payroll:item_update'
    delete_url_name = 'payroll:item_delete'


class SalaryItemListView(SalaryItemConfig, CrudListView):
    columns = [('Employé', 'employee'), ('Libellé', 'label'), ('Nature', 'kind', 'badge'),
               ('Montant', 'amount', 'money'), ('Imposable', 'is_taxable', 'bool'),
               ('Récurrent', 'is_recurring', 'bool'), ('Actif', 'is_active', 'bool')]
    search_fields = ['label', 'employee__first_name', 'employee__last_name']
    filters = [('kind', 'Nature', SalaryItem.Kind.choices),
               ('employee', 'Employé', lambda: [(e.pk, e.full_name) for e in Employee.objects.active()])]
    export_columns = [('Employé', 'employee'), ('Libellé', 'label'), ('Nature', 'get_kind_display'),
                      ('Montant', 'amount'), ('Imposable', 'is_taxable'), ('Récurrent', 'is_recurring'),
                      ('Année', 'year'), ('Mois', 'month')]
    export_filename = 'elements_salaire'

    def get_queryset(self):
        return super().get_queryset().select_related('employee')


class SalaryItemCreateView(SalaryItemConfig, CrudCreateView):
    form_title = 'Nouvel élément de salaire'

    def get_initial(self):
        return {'employee': self.request.GET.get('employe')}


class SalaryItemUpdateView(SalaryItemConfig, CrudUpdateView):
    pass


class SalaryItemDeleteView(SalaryItemConfig, CrudDeleteView):
    pass
