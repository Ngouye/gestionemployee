from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView

from core.crud import CrudCreateView, CrudDeleteView, CrudListView, CrudUpdateView
from core.models import Notification
from core.permissions import HRRequiredMixin, is_hr, role_required
from core.services import hr_users, notify
from core.utils import safe_next
from employees.models import Employee

from .forms import (EmployeeCommentForm, ObjectiveForm, ObjectiveProgressForm, ReviewCycleForm, ReviewForm,
                    SelfAssessmentForm)
from .models import Objective, PerformanceReview, ReviewCycle

# ---------------------------------------------------------------------------
# Campagnes
# ---------------------------------------------------------------------------


class CycleConfig(HRRequiredMixin):
    model = ReviewCycle
    form_class = ReviewCycleForm
    title = "Campagnes d'évaluation"
    icon = 'bi-clipboard-check'
    list_url_name = 'performance:cycle_list'
    create_url_name = 'performance:cycle_create'
    update_url_name = 'performance:cycle_update'
    delete_url_name = 'performance:cycle_delete'
    detail_url_name = 'performance:cycle_detail'


class CycleListView(CycleConfig, CrudListView):
    columns = [('Nom', 'name'), ('Début', 'start_date'), ('Fin', 'end_date'), ('Évaluations', 'review_count'),
               ('Finalisées', 'completed_count'), ('Statut', 'status', 'badge')]

    def get_queryset(self):
        return super().get_queryset().annotate(
            review_count=Count('reviews'),
            completed_count=Count('reviews', filter=Q(reviews__status=PerformanceReview.Status.COMPLETED)))


class CycleCreateView(CycleConfig, CrudCreateView):
    form_title = "Nouvelle campagne d'évaluation"

    def get_success_url(self):
        return self.object.get_absolute_url()


class CycleUpdateView(CycleConfig, CrudUpdateView):
    pass


class CycleDeleteView(CycleConfig, CrudDeleteView):
    pass


class CycleDetailView(HRRequiredMixin, DetailView):
    model = ReviewCycle
    template_name = 'performance/cycle_detail.html'
    context_object_name = 'cycle'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reviews = self.object.reviews.select_related('employee__department', 'reviewer')
        stats = reviews.aggregate(total=Count('id'), avg=Avg('overall_rating'),
                                  done=Count('id', filter=Q(status=PerformanceReview.Status.COMPLETED)))
        context.update({'reviews': reviews, 'stats': stats,
                        'missing': Employee.objects.active().exclude(reviews__cycle=self.object).count()})
        return context


@role_required(is_hr)
@require_POST
def cycle_generate(request, pk):
    cycle = get_object_or_404(ReviewCycle, pk=pk)
    fallback = hr_users().first()
    created = 0
    for employee in Employee.objects.active().exclude(reviews__cycle=cycle).select_related('manager__user'):
        reviewer = employee.manager.user if employee.manager and employee.manager.user else fallback
        review = PerformanceReview.objects.create(cycle=cycle, employee=employee, reviewer=reviewer)
        created += 1
        if reviewer:
            notify(reviewer, f'Évaluation à réaliser : {employee}', str(cycle), review.get_absolute_url(), email=False)
        if employee.user:
            notify(employee.user, f'Campagne d’évaluation : {cycle}',
                   'Vous pouvez dès maintenant rédiger votre auto-évaluation.', review.get_absolute_url(),
                   email=False)
    if cycle.status == ReviewCycle.Status.PLANNED:
        cycle.status = ReviewCycle.Status.IN_PROGRESS
        cycle.save(update_fields=['status', 'updated_at'])
    messages.success(request, f'{created} évaluation(s) créée(s).')
    return redirect(cycle.get_absolute_url())


# ---------------------------------------------------------------------------
# Évaluations
# ---------------------------------------------------------------------------

@login_required
def my_reviews(request):
    employee = request.user.employee_profile
    context = {
        'my_reviews': employee.reviews.select_related('cycle', 'reviewer') if employee else [],
        'to_do': PerformanceReview.objects.filter(reviewer=request.user).select_related('cycle', 'employee'),
        'objectives': employee.objectives.select_related('cycle') if employee else [],
    }
    return render(request, 'performance/my_reviews.html', context)


def _review_access(user, review):
    own = user.employee_profile
    return {
        'is_employee': own is not None and own.pk == review.employee_id,
        'is_reviewer': review.reviewer_id == user.pk,
        'is_hr': user.is_hr,
    }


class ReviewDetailView(LoginRequiredMixin, DetailView):
    model = PerformanceReview
    template_name = 'performance/review_detail.html'
    context_object_name = 'review'

    def get_object(self, queryset=None):
        review = super().get_object(queryset)
        access = _review_access(self.request.user, review)
        if not any(access.values()):
            raise PermissionDenied
        self.access = access
        return review

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        review = self.object
        pending = review.status == PerformanceReview.Status.PENDING
        can_review = pending and (self.access['is_reviewer'] or self.access['is_hr']) \
            and not self.access['is_employee']
        context.update(self.access)
        context['show_ratings'] = not pending or not self.access['is_employee'] or self.access['is_hr']
        context['review_form'] = ReviewForm(instance=review) if can_review else None
        context['self_form'] = SelfAssessmentForm(instance=review) if pending and self.access['is_employee'] else None
        context['comment_form'] = (EmployeeCommentForm(instance=review)
                                   if not pending and self.access['is_employee'] else None)
        context['objectives'] = review.employee.objectives.filter(Q(cycle=review.cycle) | Q(cycle__isnull=True))
        return context


@login_required
@require_POST
def review_save(request, pk):
    review = get_object_or_404(PerformanceReview, pk=pk)
    access = _review_access(request.user, review)
    form_type = request.POST.get('form')
    pending = review.status == PerformanceReview.Status.PENDING

    if form_type == 'review' and pending and (access['is_reviewer'] or access['is_hr']) and not access['is_employee']:
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            review = form.save(commit=False)
            if form.cleaned_data.get('finalize'):
                review.status = PerformanceReview.Status.COMPLETED
                review.completed_at = timezone.now()
            review.save()
            if review.status == PerformanceReview.Status.COMPLETED and review.employee.user:
                notify(review.employee.user, 'Votre évaluation est disponible', str(review.cycle),
                       review.get_absolute_url(), Notification.Level.SUCCESS)
            messages.success(request, 'Évaluation enregistrée.')
        else:
            messages.error(request, 'Veuillez corriger le formulaire : ' + '; '.join(
                str(e) for errors in form.errors.values() for e in errors))
    elif form_type == 'self' and pending and access['is_employee']:
        form = SelfAssessmentForm(request.POST, instance=review)
        if form.is_valid():
            form.save()
            messages.success(request, 'Auto-évaluation enregistrée.')
    elif form_type == 'comment' and not pending and access['is_employee']:
        form = EmployeeCommentForm(request.POST, instance=review)
        if form.is_valid():
            form.save()
            messages.success(request, 'Commentaire enregistré.')
    else:
        raise PermissionDenied
    return redirect(review.get_absolute_url())


# ---------------------------------------------------------------------------
# Objectifs
# ---------------------------------------------------------------------------

def _can_manage_objective(user, employee):
    return user.is_hr or employee.is_managed_by(user)


class ObjectiveListView(LoginRequiredMixin, CrudListView):
    model = Objective
    title = 'Objectifs'
    icon = 'bi-bullseye'
    list_url_name = 'performance:objective_list'
    create_url_name = 'performance:objective_create'
    update_url_name = 'performance:objective_update'
    columns = [('Employé', 'employee'), ('Objectif', 'title'), ('Échéance', 'due_date'),
               ('Avancement', 'progress', 'progress'), ('Statut', 'status', 'badge')]
    search_fields = ['title', 'employee__first_name', 'employee__last_name']
    filters = [('status', 'Statut', Objective.Status.choices),
               ('cycle', 'Campagne', lambda: ReviewCycle.objects.values_list('pk', 'name'))]

    def get_queryset(self):
        queryset = super().get_queryset().select_related('employee', 'cycle')
        user = self.request.user
        if user.is_hr:
            return queryset
        own = user.employee_profile
        return queryset.filter(Q(employee=own) | Q(employee__manager=own)) if own else queryset.none()


class ObjectiveCreateView(LoginRequiredMixin, CrudCreateView):
    model = Objective
    form_class = ObjectiveForm
    title = 'Objectifs'
    list_url_name = 'performance:objective_list'
    form_title = 'Nouvel objectif'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not (request.user.is_hr or (
                request.user.employee_profile and request.user.employee_profile.subordinates.exists())):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        return {'employee': self.request.GET.get('employe')}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        if self.object.employee.user:
            notify(self.object.employee.user, f'Nouvel objectif : {self.object.title}', '',
                   reverse('performance:mine'), email=False)
        return response


class ObjectiveUpdateView(LoginRequiredMixin, CrudUpdateView):
    model = Objective
    title = 'Objectifs'
    list_url_name = 'performance:objective_list'

    def get_object(self, queryset=None):
        objective = super().get_object(queryset)
        own = self.request.user.employee_profile
        self.can_manage = _can_manage_objective(self.request.user, objective.employee)
        if not (self.can_manage or (own and own.pk == objective.employee_id)):
            raise PermissionDenied
        return objective

    def get_form_class(self):
        return ObjectiveForm if self.can_manage else ObjectiveProgressForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.can_manage:
            kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        return safe_next(self.request, reverse('performance:objective_list'))


class ObjectiveDeleteView(LoginRequiredMixin, CrudDeleteView):
    model = Objective
    title = 'Objectifs'
    list_url_name = 'performance:objective_list'

    def get_object(self, queryset=None):
        objective = super().get_object(queryset)
        if not _can_manage_objective(self.request.user, objective.employee):
            raise PermissionDenied
        return objective
