from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView

from core.crud import CrudCreateView, CrudDeleteView, CrudListView, CrudUpdateView
from core.files import serve_file
from core.models import Notification
from core.permissions import EmployeeRequiredMixin, HRRequiredMixin, is_hr, role_required
from core.services import notify, notify_hr
from core.utils import safe_next
from employees.access import can_view_employee
from organization.models import Department

from .forms import ExpenseCategoryForm, ExpenseClaimForm, ExpenseDecisionForm
from .models import ExpenseCategory, ExpenseClaim


class MyExpensesView(EmployeeRequiredMixin, ListView):
    template_name = 'expenses/my_expenses.html'
    context_object_name = 'claims'
    paginate_by = 20

    def get_queryset(self):
        return self.employee.expense_claims.select_related('category')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        claims = self.employee.expense_claims
        context['totals'] = {
            'submitted': claims.filter(status=ExpenseClaim.Status.SUBMITTED).aggregate(s=Sum('amount'))['s'] or 0,
            'approved': claims.filter(status=ExpenseClaim.Status.APPROVED).aggregate(s=Sum('amount'))['s'] or 0,
            'paid': claims.filter(status=ExpenseClaim.Status.PAID,
                                  paid_at__year=timezone.localdate().year).aggregate(s=Sum('amount'))['s'] or 0,
        }
        return context


class ExpenseCreateView(EmployeeRequiredMixin, CreateView):
    model = ExpenseClaim
    form_class = ExpenseClaimForm
    template_name = 'core/crud_form.html'
    success_url = reverse_lazy('expenses:mine')

    def form_valid(self, form):
        form.instance.employee = self.employee
        response = super().form_valid(form)
        claim = self.object
        title = f'Note de frais à valider : {self.employee}'
        body = f'{claim.title} — {claim.amount:.0f} ({claim.category})'
        manager = self.employee.manager
        if manager and manager.user:
            notify(manager.user, title, body, claim.get_absolute_url(), Notification.Level.WARNING)
        else:
            notify_hr(title, body, claim.get_absolute_url(), Notification.Level.WARNING, exclude=self.request.user)
        messages.success(self.request, 'Note de frais soumise pour validation.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({'form_title': 'Nouvelle note de frais', 'page_title': 'Notes de frais',
                        'cancel_url': reverse('expenses:mine')})
        return context


class ExpenseDetailView(LoginRequiredMixin, DetailView):
    model = ExpenseClaim
    template_name = 'expenses/expense_detail.html'
    context_object_name = 'claim'

    def get_object(self, queryset=None):
        claim = super().get_object(queryset)
        if not can_view_employee(self.request.user, claim.employee):
            raise PermissionDenied
        return claim

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_review'] = self.object.can_be_reviewed_by(self.request.user)
        context['can_pay'] = self.request.user.is_hr and self.object.status == ExpenseClaim.Status.APPROVED
        context['can_delete'] = (self.object.status == ExpenseClaim.Status.SUBMITTED
                                 and self.object.employee.user_id == self.request.user.pk)
        return context


@login_required
@require_POST
def expense_decide(request, pk):
    claim = get_object_or_404(ExpenseClaim, pk=pk)
    if not claim.can_be_reviewed_by(request.user):
        raise PermissionDenied
    form = ExpenseDecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, ' '.join(form.non_field_errors()) or 'Décision invalide.')
        return redirect(claim.get_absolute_url())
    approved = form.cleaned_data['decision'] == 'approve'
    claim.status = ExpenseClaim.Status.APPROVED if approved else ExpenseClaim.Status.REJECTED
    claim.reviewed_by = request.user
    claim.reviewed_at = timezone.now()
    claim.review_comment = form.cleaned_data.get('comment', '')
    claim.save()
    verdict = 'approuvée' if approved else 'refusée'
    if claim.employee.user:
        notify(claim.employee.user, f'Note de frais {verdict}', f'{claim.title}. {claim.review_comment}'.strip(),
               claim.get_absolute_url(), Notification.Level.SUCCESS if approved else Notification.Level.DANGER)
    if approved and not request.user.is_hr:
        notify_hr('Note de frais à rembourser', f'{claim.employee} — {claim.title}', claim.get_absolute_url())
    messages.success(request, f'Note de frais {verdict}.')
    return redirect(safe_next(request, reverse('core:approvals')))


@role_required(is_hr)
@require_POST
def expense_mark_paid(request, pk):
    claim = get_object_or_404(ExpenseClaim, pk=pk, status=ExpenseClaim.Status.APPROVED)
    claim.status = ExpenseClaim.Status.PAID
    claim.paid_at = timezone.localdate()
    claim.save()
    if claim.employee.user:
        notify(claim.employee.user, 'Note de frais remboursée', claim.title, claim.get_absolute_url(),
               Notification.Level.SUCCESS)
    messages.success(request, 'Note de frais marquée comme remboursée.')
    return redirect(claim.get_absolute_url())


@login_required
@require_POST
def expense_delete(request, pk):
    claim = get_object_or_404(ExpenseClaim, pk=pk, status=ExpenseClaim.Status.SUBMITTED,
                              employee__user=request.user)
    claim.receipt.delete(save=False)
    claim.delete()
    messages.success(request, 'Note de frais supprimée.')
    return redirect('expenses:mine')


@login_required
def expense_receipt(request, pk):
    claim = get_object_or_404(ExpenseClaim, pk=pk)
    if not can_view_employee(request.user, claim.employee):
        raise PermissionDenied
    return serve_file(claim.receipt, as_attachment=False)


class ExpenseListView(HRRequiredMixin, CrudListView):
    model = ExpenseClaim
    title = 'Notes de frais'
    icon = 'bi-receipt'
    list_url_name = 'expenses:list'
    detail_url_name = 'expenses:detail'
    columns = [('Employé', 'employee'), ('Objet', 'title'), ('Catégorie', 'category'),
               ('Date', 'expense_date'), ('Montant', 'amount', 'money'), ('Statut', 'status', 'badge')]
    search_fields = ['title', 'employee__first_name', 'employee__last_name']
    filters = [
        ('status', 'Statut', ExpenseClaim.Status.choices),
        ('category', 'Catégorie', lambda: ExpenseCategory.objects.values_list('pk', 'name')),
        ('employee__department', 'Département', lambda: Department.objects.values_list('pk', 'name')),
    ]
    export_columns = [('Matricule', 'employee.employee_id'), ('Employé', 'employee'), ('Objet', 'title'),
                      ('Catégorie', 'category'), ('Date', 'expense_date'), ('Montant', 'amount'),
                      ('Statut', 'get_status_display'), ('Remboursée le', 'paid_at')]
    export_filename = 'notes_de_frais'

    def get_queryset(self):
        return super().get_queryset().select_related('employee', 'category')


class CategoryConfig(HRRequiredMixin):
    model = ExpenseCategory
    form_class = ExpenseCategoryForm
    title = 'Catégories de frais'
    icon = 'bi-tags'
    list_url_name = 'expenses:category_list'
    create_url_name = 'expenses:category_create'
    update_url_name = 'expenses:category_update'
    delete_url_name = 'expenses:category_delete'


class CategoryListView(CategoryConfig, CrudListView):
    columns = [('Nom', 'name'), ('Description', 'description'), ('Plafond', 'max_amount', 'money'),
               ('Active', 'is_active', 'bool')]


class CategoryCreateView(CategoryConfig, CrudCreateView):
    form_title = 'Nouvelle catégorie'


class CategoryUpdateView(CategoryConfig, CrudUpdateView):
    pass


class CategoryDeleteView(CategoryConfig, CrudDeleteView):
    pass
