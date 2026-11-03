from collections import defaultdict
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView, UpdateView

from accounts.services import create_account_for_employee
from core.crud import CrudCreateView, CrudDeleteView, CrudListView, CrudUpdateView
from core.exports import export_response
from core.files import serve_file
from core.models import AuditLog
from core.permissions import EmployeeRequiredMixin, HRRequiredMixin, is_hr, role_required
from core.services import log_action, notify_hr
from leaves.services import balances_for
from organization.models import Department, Position
from payroll.models import Payslip
from recruitment.models import Application

from . import importers
from .access import can_view_employee
from .letters import render_employment_letter
from .forms import (AccountForm, ContractForm, EmployeeDocumentForm, EmployeeForm, EmployeeImportForm,
                    EmployeeSelfForm, InitialContractForm)
from .models import Contract, Employee, EmployeeDocument


# ---------------------------------------------------------------------------
# Liste, fiche, création, modification
# ---------------------------------------------------------------------------

class EmployeeListView(CrudListView):
    model = Employee
    template_name = 'employees/employee_list.html'
    title = 'Employés'
    icon = 'bi-people'
    list_url_name = 'employees:list'
    search_fields = ['first_name', 'last_name', 'email', 'employee_id', 'phone', 'position__title']
    filters = [
        ('department', 'Département', lambda: Department.objects.values_list('pk', 'name')),
        ('position', 'Poste', lambda: Position.objects.values_list('pk', 'title')),
        ('status', 'Statut', Employee.Status.choices),
        ('gender', 'Genre', Employee.Gender.choices),
    ]
    export_columns = [
        ('Matricule', 'employee_id'), ('Prénom', 'first_name'), ('Nom', 'last_name'),
        ('E-mail', 'email'), ('Téléphone', 'phone'), ('Genre', 'get_gender_display'),
        ('Date de naissance', 'date_of_birth'), ('Département', 'department'), ('Poste', 'position'),
        ('Responsable', 'manager'), ("Date d'embauche", 'hire_date'), ('Statut', 'get_status_display'),
        ('Type de contrat', 'current_contract.get_contract_type_display'),
        ('Salaire de base', 'base_salary'), ('N° sécurité sociale', 'social_security_number'),
    ]
    export_filename = 'employes'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('accounts:login')}?next={request.path}")
        if not (request.user.is_hr or (request.user.employee_profile
                                       and request.user.employee_profile.subordinates.exists())):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset().select_related('department', 'position', 'manager', 'user')
        queryset = queryset.prefetch_related('contracts')
        if not self.request.user.is_hr:
            queryset = queryset.filter(manager=self.request.user.employee_profile)
        elif not self.request.GET.get('status'):
            queryset = queryset.exclude(status=Employee.Status.TERMINATED)
        return queryset

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get('export') and not self.request.user.is_hr:
            raise PermissionDenied
        return super().render_to_response(context, **response_kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_team_view'] = not self.request.user.is_hr
        if context['is_team_view']:
            context['page_title'] = 'Mon équipe'
        return context


class EmployeeDetailView(DetailView):
    model = Employee
    template_name = 'employees/employee_detail.html'
    context_object_name = 'employee'

    def get_queryset(self):
        return Employee.objects.select_related('department', 'position', 'manager', 'user')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('accounts:login')}?next={request.path}")
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        employee = super().get_object(queryset)
        if not can_view_employee(self.request.user, employee):
            raise PermissionDenied
        return employee

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = self.object
        user = self.request.user
        is_self = user.employee_profile is not None and user.employee_profile.pk == employee.pk
        today = timezone.localdate()
        context.update({
            'is_self': is_self,
            'can_edit': user.is_hr,
            'can_view_sensitive': user.is_hr or is_self,
            'contracts': employee.contracts.select_related('position'),
            'documents': employee.documents.all() if user.is_hr
            else employee.documents.filter(visible_to_employee=True),
            'subordinates': employee.subordinates.filter(status=Employee.Status.ACTIVE),
            'balances': balances_for(employee, today.year),
            'leave_requests': employee.leave_requests.select_related('leave_type')[:10],
            'attendances': employee.attendances.filter(date__gte=today - timedelta(days=30))[:31],
            'payslips': Payslip.objects.filter(employee=employee).select_related('period')[:12]
            if (user.is_hr or is_self) else [],
            'reviews': employee.reviews.select_related('cycle', 'reviewer')[:5],
            'objectives': employee.objectives.all()[:10],
            'trainings': employee.training_participations.select_related('training')[:10],
            'document_form': EmployeeDocumentForm() if user.is_hr else None,
        })
        return context


class EmployeeCreateView(HRRequiredMixin, CrudCreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = 'employees/employee_form.html'
    title = 'Employés'
    list_url_name = 'employees:list'
    form_title = 'Nouvel employé'

    def get_initial(self):
        initial = super().get_initial()
        initial['hire_date'] = timezone.localdate()
        application_id = self.request.GET.get('candidature')
        if application_id:
            application = Application.objects.filter(pk=application_id).select_related('job').first()
            if application:
                initial.update({
                    'first_name': application.first_name, 'last_name': application.last_name,
                    'email': application.email, 'phone': application.phone,
                    'department': application.job.department_id, 'position': application.job.position_id,
                })
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault('contract_form', InitialContractForm(prefix='contract'))
        context.setdefault('account_form', AccountForm(prefix='account'))
        return context

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        contract_form = InitialContractForm(request.POST, prefix='contract')
        account_form = AccountForm(request.POST, prefix='account')
        if not (form.is_valid() and contract_form.is_valid() and account_form.is_valid()):
            messages.error(request, 'Veuillez corriger les erreurs du formulaire.')
            return self.render_to_response(self.get_context_data(
                form=form, contract_form=contract_form, account_form=account_form))

        with transaction.atomic():
            employee = form.save()
            contract = contract_form.save(commit=False)
            contract.employee = employee
            contract.position = employee.position
            contract.start_date = employee.hire_date
            contract.save()
            password = None
            if account_form.cleaned_data.get('create_account'):
                try:
                    _user, password = create_account_for_employee(employee, account_form.cleaned_data['role'])
                except ValueError as exc:
                    messages.warning(request, str(exc))
            application_id = request.GET.get('candidature')
            if application_id:
                    Application.objects.filter(pk=application_id).update(
                    hired_employee=employee, stage=Application.Stage.HIRED)

        messages.success(request, f'Employé {employee} créé (matricule {employee.employee_id}).')
        if password:
            messages.info(request, f'Compte créé pour {employee.email}. Mot de passe temporaire : '
                                   f'{password} — à communiquer à l\'employé.')
        return redirect(employee.get_absolute_url())


class EmployeeUpdateView(HRRequiredMixin, CrudUpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = 'employees/employee_form.html'
    title = 'Employés'
    list_url_name = 'employees:list'

    def get_success_url(self):
        return self.object.get_absolute_url()


class EmployeeDeleteView(HRRequiredMixin, CrudDeleteView):
    model = Employee
    title = 'Employés'
    list_url_name = 'employees:list'
    template_name = 'employees/employee_confirm_delete.html'


class MyProfileUpdateView(EmployeeRequiredMixin, UpdateView):
    form_class = EmployeeSelfForm
    template_name = 'core/crud_form.html'

    def get_object(self, queryset=None):
        return self.employee

    def form_valid(self, form):
        messages.success(self.request, 'Vos informations ont été mises à jour.')
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({'form_title': 'Modifier mes informations', 'page_title': 'Mon profil',
                        'cancel_url': self.object.get_absolute_url()})
        return context


@login_required
def my_profile(request):
    employee = request.user.employee_profile
    if employee is None:
        return redirect('accounts:profile')
    return redirect(employee.get_absolute_url())


@login_required
def employee_photo(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    return serve_file(employee.photo, as_attachment=False)


@role_required(is_hr)
@require_POST
def employee_account(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    role = request.POST.get('role') or (employee.user.role if employee.user else 'EMPLOYEE')
    try:
        user, password = create_account_for_employee(employee, role)
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f'Accès configuré pour {user.email}. Mot de passe temporaire : {password}')
    return redirect(employee.get_absolute_url())


# ---------------------------------------------------------------------------
# Annuaire et organigramme (accessibles à tous les collaborateurs)
# ---------------------------------------------------------------------------

class DirectoryView(ListView):
    template_name = 'employees/directory.html'
    paginate_by = 24
    context_object_name = 'employees'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('accounts:login')}?next={request.path}")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Employee.objects.active().select_related('department', 'position')
        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query)
                                       | Q(position__title__icontains=query) | Q(email__icontains=query))
        department = self.request.GET.get('department')
        if department:
            queryset = queryset.filter(department_id=department)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['departments'] = Department.objects.filter(is_active=True)
        context['q'] = self.request.GET.get('q', '')
        context['department'] = self.request.GET.get('department', '')
        return context


@login_required
def org_chart(request):
    employees = list(Employee.objects.active().select_related('position', 'department'))
    children = defaultdict(list)
    ids = {e.pk for e in employees}
    roots = []
    for employee in employees:
        if employee.manager_id and employee.manager_id in ids:
            children[employee.manager_id].append(employee)
        else:
            roots.append(employee)

    def build(employee, depth=0):
        return {'employee': employee,
                'children': [build(child, depth + 1) for child in children.get(employee.pk, [])] if depth < 12 else []}

    tree = [build(root) for root in roots]
    return render(request, 'employees/org_chart.html', {'tree': tree, 'total': len(employees)})


# ---------------------------------------------------------------------------
# Contrats
# ---------------------------------------------------------------------------

class ContractListView(HRRequiredMixin, CrudListView):
    model = Contract
    title = 'Contrats'
    icon = 'bi-file-earmark-text'
    list_url_name = 'employees:contract_list'
    update_url_name = 'employees:contract_update'
    delete_url_name = 'employees:contract_delete'
    columns = [('Référence', 'reference'), ('Employé', 'employee'), ('Type', 'contract_type', 'badge'),
               ('Début', 'start_date'), ('Fin', 'end_date'), ('Salaire de base', 'base_salary', 'money'),
               ('Statut', 'status', 'badge')]
    search_fields = ['reference', 'employee__first_name', 'employee__last_name']
    filters = [('contract_type', 'Type', Contract.Type.choices), ('status', 'Statut', Contract.Status.choices)]
    export_columns = [('Référence', 'reference'), ('Matricule', 'employee.employee_id'), ('Employé', 'employee'),
                      ('Type', 'get_contract_type_display'), ('Poste', 'position'), ('Début', 'start_date'),
                      ('Fin', 'end_date'), ("Fin d'essai", 'trial_end_date'), ('Salaire de base', 'base_salary'),
                      ('Statut', 'get_status_display')]
    export_filename = 'contrats'
    subtitle = 'Suivi des contrats, échéances et périodes d\'essai'

    def get_queryset(self):
        queryset = super().get_queryset().select_related('employee', 'position')
        if self.request.GET.get('echeance') == '30':
            today = timezone.localdate()
            queryset = queryset.filter(status=Contract.Status.ACTIVE, end_date__gte=today,
                                       end_date__lte=today + timedelta(days=30))
        return queryset


class ContractFormMixin(HRRequiredMixin):
    model = Contract
    form_class = ContractForm
    title = 'Contrats'
    list_url_name = 'employees:contract_list'

    def get_success_url(self):
        return reverse('employees:detail', args=[self.object.employee_id]) + '#contrats'


class ContractCreateView(ContractFormMixin, CrudCreateView):
    def dispatch(self, request, *args, **kwargs):
        self.employee = get_object_or_404(Employee, pk=kwargs['employee_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_title(self):
        return f'Nouveau contrat — {self.employee}'

    def get_initial(self):
        current = self.employee.current_contract
        return {'position': self.employee.position_id, 'start_date': timezone.localdate(),
                'base_salary': current.base_salary if current else None}

    def form_valid(self, form):
        form.instance.employee = self.employee
        response = super().form_valid(form)
        if form.instance.status == Contract.Status.ACTIVE:
            (self.employee.contracts.filter(status=Contract.Status.ACTIVE)
             .exclude(pk=form.instance.pk).update(status=Contract.Status.ENDED))
        return response


class ContractUpdateView(ContractFormMixin, CrudUpdateView):
    pass


class ContractDeleteView(ContractFormMixin, CrudDeleteView):
    pass


@login_required
def contract_download(request, pk):
    contract = get_object_or_404(Contract.objects.select_related('employee'), pk=pk)
    own = request.user.employee_profile
    if not (request.user.is_hr or (own and own.pk == contract.employee_id)):
        raise PermissionDenied
    return serve_file(contract.document)


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@role_required(is_hr)
@require_POST
def document_upload(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    form = EmployeeDocumentForm(request.POST, request.FILES)
    if form.is_valid():
        document = form.save(commit=False)
        document.employee = employee
        document.uploaded_by = request.user
        document.save()
        messages.success(request, f'Document « {document.title} » ajouté.')
    else:
        errors = '; '.join(f'{form.fields[f].label if f in form.fields else f} : {", ".join(e)}'
                           for f, e in form.errors.items())
        messages.error(request, f'Document non enregistré — {errors}')
    return redirect(reverse('employees:detail', args=[pk]) + '#documents')


@login_required
def document_download(request, pk):
    document = get_object_or_404(EmployeeDocument, pk=pk)
    own = request.user.employee_profile
    allowed = request.user.is_hr or (own and own.pk == document.employee_id and document.visible_to_employee)
    if not allowed:
        raise PermissionDenied
    return serve_file(document.file)


@role_required(is_hr)
@require_POST
def document_delete(request, pk):
    document = get_object_or_404(EmployeeDocument, pk=pk)
    employee_id = document.employee_id
    document.file.delete(save=False)
    document.delete()
    messages.success(request, 'Document supprimé.')
    return redirect(reverse('employees:detail', args=[employee_id]) + '#documents')


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

@role_required(is_hr)
def employee_import(request):
    if request.GET.get('modele'):
        return export_response('modele_import_employes', importers.COLUMNS, [importers.EXAMPLE_ROW],
                               sheet_title='Employés')
    report = None
    form = EmployeeImportForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            created, errors = importers.import_employees(form.cleaned_data['file'])
        except Exception as exc:  # fichier illisible
            messages.error(request, f'Impossible de lire le fichier : {exc}')
        else:
            report = {'created': created, 'errors': errors}
            if created:
                messages.success(request, f'{created} employé(s) importé(s).')
    return render(request, 'employees/employee_import.html', {'form': form, 'report': report})


# ---------------------------------------------------------------------------
# Attestation et certificat de travail
# ---------------------------------------------------------------------------

@role_required(is_hr)
def employment_letter(request, pk, kind):
    employee = get_object_or_404(Employee.objects.select_related('position'), pk=pk)
    if kind == 'certificat' and not employee.exit_date:
        messages.error(request, 'Le certificat de travail est délivré à la sortie : renseignez la date de sortie.')
        return redirect(employee.get_absolute_url())
    pdf = render_employment_letter(employee, kind)
    label = 'Certificat de travail' if kind == 'certificat' else 'Attestation de travail'
    log_action(AuditLog.Action.ACTION, employee, f'{label} délivré(e) à {employee}')
    response = HttpResponse(pdf, content_type='application/pdf')
    filename = f'{kind}_de_travail_{employee.employee_id}.pdf'
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@login_required
@require_POST
def request_attestation(request):
    employee = request.user.employee_profile
    if employee is None:
        raise PermissionDenied
    notify_hr(f"Demande d'attestation de travail : {employee}",
              "Le collaborateur demande une attestation de travail.", employee.get_absolute_url())
    messages.success(request, 'Votre demande a été transmise aux ressources humaines.')
    return redirect(employee.get_absolute_url())
