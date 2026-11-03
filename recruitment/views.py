from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, UpdateView

from core.crud import CrudCreateView, CrudDeleteView, CrudListView, CrudUpdateView
from core.files import serve_file
from core.permissions import HRRequiredMixin, is_hr, role_required
from core.services import notify, notify_hr
from core.utils import safe_next
from organization.models import Department

from .forms import ApplicationForm, InterviewFeedbackForm, InterviewForm, JobOpeningForm, PublicApplicationForm
from .models import Application, Interview, JobOpening

# ---------------------------------------------------------------------------
# Offres d'emploi
# ---------------------------------------------------------------------------


class JobConfig(HRRequiredMixin):
    model = JobOpening
    form_class = JobOpeningForm
    title = "Offres d'emploi"
    icon = 'bi-megaphone'
    list_url_name = 'recruitment:job_list'
    create_url_name = 'recruitment:job_create'
    update_url_name = 'recruitment:job_update'
    delete_url_name = 'recruitment:job_delete'
    detail_url_name = 'recruitment:job_detail'


class JobListView(JobConfig, CrudListView):
    columns = [('Intitulé', 'title'), ('Département', 'department'), ('Contrat', 'contract_type', 'badge'),
               ('Lieu', 'location'), ('Candidatures', 'application_count'), ('Date limite', 'closing_date'),
               ('Statut', 'status', 'badge')]
    search_fields = ['title', 'location']
    filters = [('status', 'Statut', JobOpening.Status.choices),
               ('department', 'Département', lambda: Department.objects.values_list('pk', 'name'))]

    def get_queryset(self):
        return super().get_queryset().select_related('department').annotate(
            application_count=Count('applications'))


class JobCreateView(JobConfig, CrudCreateView):
    form_title = "Nouvelle offre d'emploi"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class JobUpdateView(JobConfig, CrudUpdateView):
    def get_success_url(self):
        return self.object.get_absolute_url()


class JobDeleteView(JobConfig, CrudDeleteView):
    pass


class JobDetailView(HRRequiredMixin, DetailView):
    """Pipeline de recrutement (vue Kanban)."""

    model = JobOpening
    template_name = 'recruitment/job_detail.html'
    context_object_name = 'job'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        applications = self.object.applications.annotate(interview_count=Count('interviews'))
        context['columns'] = [
            {'stage': value, 'label': label, 'applications': [a for a in applications if a.stage == value]}
            for value, label in Application.Stage.choices
        ]
        context['careers_url'] = self.request.build_absolute_uri(
            reverse('recruitment:careers_detail', args=[self.object.pk]))
        return context


# ---------------------------------------------------------------------------
# Candidatures
# ---------------------------------------------------------------------------

class ApplicationConfig(HRRequiredMixin):
    model = Application
    form_class = ApplicationForm
    title = 'Candidatures'
    icon = 'bi-person-lines-fill'
    list_url_name = 'recruitment:application_list'
    create_url_name = 'recruitment:application_create'
    update_url_name = 'recruitment:application_update'
    delete_url_name = 'recruitment:application_delete'
    detail_url_name = 'recruitment:application_detail'


class ApplicationListView(ApplicationConfig, CrudListView):
    columns = [('Candidat', 'full_name'), ('Offre', 'job'), ('E-mail', 'email'), ('Source', 'get_source_display'),
               ('Évaluation', 'get_rating_display'), ('Étape', 'stage', 'badge'), ('Reçue le', 'created_at')]
    search_fields = ['first_name', 'last_name', 'email', 'job__title']
    filters = [('stage', 'Étape', Application.Stage.choices), ('source', 'Source', Application.Source.choices),
               ('job', 'Offre', lambda: JobOpening.objects.values_list('pk', 'title'))]
    export_columns = [('Prénom', 'first_name'), ('Nom', 'last_name'), ('E-mail', 'email'), ('Téléphone', 'phone'),
                      ('Offre', 'job'), ('Source', 'get_source_display'), ('Étape', 'get_stage_display'),
                      ('Évaluation', 'rating'), ('Reçue le', 'created_at')]
    export_filename = 'candidatures'

    def get_queryset(self):
        return super().get_queryset().select_related('job')


class ApplicationCreateView(ApplicationConfig, CrudCreateView):
    form_title = 'Nouvelle candidature'

    def get_initial(self):
        return {'job': self.request.GET.get('offre'), 'source': Application.Source.OTHER}

    def get_success_url(self):
        return self.object.get_absolute_url()


class ApplicationUpdateView(ApplicationConfig, CrudUpdateView):
    def get_success_url(self):
        return self.object.get_absolute_url()


class ApplicationDeleteView(ApplicationConfig, CrudDeleteView):
    pass


class ApplicationDetailView(HRRequiredMixin, DetailView):
    model = Application
    template_name = 'recruitment/application_detail.html'
    context_object_name = 'application'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['interviews'] = self.object.interviews.select_related('interviewer')
        context['stages'] = Application.Stage.choices
        context['interview_form'] = InterviewForm(initial={'scheduled_at': timezone.localtime().replace(
            minute=0, second=0, microsecond=0) + timedelta(days=1), 'interviewer': self.request.user.pk})
        return context


@role_required(is_hr)
@require_POST
def application_move(request, pk):
    application = get_object_or_404(Application, pk=pk)
    stage = request.POST.get('stage')
    if stage not in Application.Stage.values:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'error': 'Étape inconnue'}, status=400)
        messages.error(request, 'Étape inconnue.')
        return redirect(application.get_absolute_url())
    application.stage = stage
    application.save(update_fields=['stage', 'updated_at'])
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'stage': stage, 'label': application.get_stage_display()})
    messages.success(request, f'{application.full_name} → {application.get_stage_display()}')
    return redirect(safe_next(request, application.get_absolute_url()))


@role_required(is_hr)
def application_resume(request, pk):
    application = get_object_or_404(Application, pk=pk)
    return serve_file(application.resume, as_attachment=False)


# ---------------------------------------------------------------------------
# Entretiens
# ---------------------------------------------------------------------------

@role_required(is_hr)
@require_POST
def interview_create(request, application_pk):
    application = get_object_or_404(Application, pk=application_pk)
    form = InterviewForm(request.POST)
    if form.is_valid():
        interview = form.save(commit=False)
        interview.application = application
        interview.save()
        if application.stage in (Application.Stage.NEW, Application.Stage.SCREENING):
            application.stage = Application.Stage.INTERVIEW
            application.save(update_fields=['stage', 'updated_at'])
        if interview.interviewer and interview.interviewer != request.user:
            notify(interview.interviewer, f'Entretien planifié : {application.full_name}',
                   f'{application.job} — {timezone.localtime(interview.scheduled_at):%d/%m/%Y à %H:%M}',
                   reverse('recruitment:interview_feedback', args=[interview.pk]))
        messages.success(request, 'Entretien planifié.')
    else:
        messages.error(request, 'Entretien non enregistré : vérifiez la date et les champs obligatoires.')
    return redirect(application.get_absolute_url())


class InterviewListView(LoginRequiredMixin, CrudListView):
    model = Interview
    title = 'Entretiens'
    icon = 'bi-camera-video'
    list_url_name = 'recruitment:interview_list'
    columns = [('Date', 'scheduled_at'), ('Candidat', 'application.full_name'), ('Offre', 'application.job'),
               ('Format', 'get_mode_display'), ('Intervieweur', 'interviewer'), ('Statut', 'status', 'badge')]
    filters = [('status', 'Statut', Interview.Status.choices)]
    detail_url_name = 'recruitment:interview_feedback'

    def get_queryset(self):
        queryset = super().get_queryset().select_related('application__job', 'interviewer')
        if not self.request.user.is_hr:
            queryset = queryset.filter(interviewer=self.request.user)
        if self.request.GET.get('periode') != 'tous':
            queryset = queryset.filter(scheduled_at__gte=timezone.now() - timedelta(days=1))
        return queryset.order_by('scheduled_at')


class InterviewFeedbackView(LoginRequiredMixin, UpdateView):
    model = Interview
    template_name = 'core/crud_form.html'

    def get_form_class(self):
        return InterviewForm if self.request.user.is_hr else InterviewFeedbackForm

    def get_object(self, queryset=None):
        interview = super().get_object(queryset)
        if not (self.request.user.is_hr or interview.interviewer_id == self.request.user.pk):
            raise PermissionDenied
        return interview

    def form_valid(self, form):
        messages.success(self.request, 'Entretien mis à jour.')
        return super().form_valid(form)

    def get_success_url(self):
        if self.request.user.is_hr:
            return self.object.application.get_absolute_url()
        return reverse('recruitment:interview_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({'form_title': str(self.object), 'page_title': 'Entretiens',
                        'cancel_url': reverse('recruitment:interview_list')})
        return context


@role_required(is_hr)
@require_POST
def interview_delete(request, pk):
    interview = get_object_or_404(Interview, pk=pk)
    application = interview.application
    interview.delete()
    messages.success(request, 'Entretien supprimé.')
    return redirect(application.get_absolute_url())


# ---------------------------------------------------------------------------
# Page carrières publique
# ---------------------------------------------------------------------------

def _published_jobs():
    today = timezone.localdate()
    return (JobOpening.objects.filter(status=JobOpening.Status.OPEN, is_public=True)
            .filter(Q(closing_date__isnull=True) | Q(closing_date__gte=today)).select_related('department'))


def careers_list(request):
    jobs = _published_jobs()
    return render(request, 'recruitment/careers_list.html', {'jobs': jobs})


def careers_detail(request, pk):
    job = get_object_or_404(_published_jobs(), pk=pk)
    form = PublicApplicationForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        application = form.save(commit=False)
        application.job = job
        application.source = Application.Source.CAREERS
        if Application.objects.filter(job=job, email__iexact=application.email).exists():
            messages.info(request, 'Nous avons déjà reçu votre candidature pour cette offre. Merci !')
            return redirect('recruitment:careers_thanks')
        application.save()
        notify_hr(f'Nouvelle candidature : {application.full_name}', f'Offre : {job}',
                  application.get_absolute_url())
        return redirect('recruitment:careers_thanks')
    return render(request, 'recruitment/careers_detail.html', {'job': job, 'form': form})


def careers_thanks(request):
    return render(request, 'recruitment/careers_thanks.html')

