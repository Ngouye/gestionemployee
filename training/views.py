from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView

from core.crud import CrudCreateView, CrudDeleteView, CrudListView, CrudUpdateView
from core.files import serve_file
from core.models import Notification
from core.permissions import HRRequiredMixin, is_hr, role_required
from core.services import notify, notify_hr

from .forms import EnrollForm, FeedbackForm, ParticipantForm, TrainingForm
from .models import Training, TrainingParticipant


class TrainingConfig(HRRequiredMixin):
    model = Training
    form_class = TrainingForm
    title = 'Formations'
    icon = 'bi-mortarboard'
    list_url_name = 'training:list'
    create_url_name = 'training:create'
    update_url_name = 'training:update'
    delete_url_name = 'training:delete'
    detail_url_name = 'training:detail'


class TrainingListView(TrainingConfig, CrudListView):
    columns = [('Intitulé', 'title'), ('Thème', 'category'), ('Organisme', 'provider'), ('Début', 'start_date'),
               ('Fin', 'end_date'), ('Format', 'get_mode_display'), ('Participants', 'participant_count'),
               ('Coût', 'cost', 'money'), ('Statut', 'status', 'badge')]
    search_fields = ['title', 'category', 'provider']
    filters = [('status', 'Statut', Training.Status.choices), ('mode', 'Format', Training.Mode.choices)]
    export_columns = [('Intitulé', 'title'), ('Thème', 'category'), ('Organisme', 'provider'),
                      ('Début', 'start_date'), ('Fin', 'end_date'), ('Durée (h)', 'duration_hours'),
                      ('Participants', 'participant_count'), ('Coût', 'cost'), ('Statut', 'get_status_display')]
    export_filename = 'formations'

    def get_queryset(self):
        return super().get_queryset().annotate(participant_count=Count(
            'participants', filter=~Q(participants__status__in=[TrainingParticipant.Status.CANCELLED,
                                                                TrainingParticipant.Status.REQUESTED])))


class TrainingCreateView(TrainingConfig, CrudCreateView):
    form_title = 'Nouvelle formation'

    def get_success_url(self):
        return self.object.get_absolute_url()


class TrainingUpdateView(TrainingConfig, CrudUpdateView):
    def get_success_url(self):
        return self.object.get_absolute_url()


class TrainingDeleteView(TrainingConfig, CrudDeleteView):
    pass


class TrainingDetailView(HRRequiredMixin, DetailView):
    model = Training
    template_name = 'training/training_detail.html'
    context_object_name = 'training'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['participants'] = self.object.participants.select_related('employee__department')
        context['enroll_form'] = EnrollForm(training=self.object)
        context['statuses'] = TrainingParticipant.Status.choices
        rated = [p.satisfaction for p in context['participants'] if p.satisfaction]
        context['avg_satisfaction'] = round(sum(rated) / len(rated), 1) if rated else None
        return context


@role_required(is_hr)
@require_POST
def enroll(request, pk):
    training = get_object_or_404(Training, pk=pk)
    form = EnrollForm(request.POST, training=training)
    if form.is_valid():
        count = 0
        for employee in form.cleaned_data['employees']:
            TrainingParticipant.objects.create(training=training, employee=employee)
            count += 1
            if employee.user:
                notify(employee.user, f'Inscription à la formation « {training} »',
                       f'Du {training.start_date:%d/%m/%Y} au {training.end_date:%d/%m/%Y}.', reverse('training:mine'))
        messages.success(request, f'{count} employé(s) inscrit(s).')
        if training.capacity is not None and training.seats_taken > training.capacity:
            messages.warning(request, 'Attention : le nombre de places disponibles est dépassé.')
    else:
        messages.error(request, 'Sélectionnez au moins un employé.')
    return redirect(training.get_absolute_url())


@role_required(is_hr)
@require_POST
def participant_update(request, pk):
    participant = get_object_or_404(TrainingParticipant, pk=pk)
    form = ParticipantForm(request.POST, request.FILES, instance=participant)
    if form.is_valid():
        previous = TrainingParticipant.objects.get(pk=pk).status
        form.save()
        if (previous == TrainingParticipant.Status.REQUESTED and participant.status
                == TrainingParticipant.Status.REGISTERED and participant.employee.user):
            notify(participant.employee.user, 'Demande de formation acceptée', str(participant.training),
                   reverse('training:mine'), Notification.Level.SUCCESS)
        messages.success(request, f'Participation de {participant.employee} mise à jour.')
    else:
        messages.error(request, 'Mise à jour impossible.')
    return redirect(participant.training.get_absolute_url())


@role_required(is_hr)
@require_POST
def participant_remove(request, pk):
    participant = get_object_or_404(TrainingParticipant, pk=pk)
    training = participant.training
    participant.delete()
    messages.success(request, 'Participant retiré.')
    return redirect(training.get_absolute_url())


@login_required
def my_trainings(request):
    employee = request.user.employee_profile
    if employee is None:
        return redirect('core:dashboard')
    participations = employee.training_participations.select_related('training')
    enrolled_ids = participations.values_list('training_id', flat=True)
    catalog = (Training.objects.filter(status=Training.Status.PLANNED, is_open_for_requests=True,
                                       start_date__gte=timezone.localdate())
               .exclude(pk__in=enrolled_ids))
    return render(request, 'training/my_trainings.html', {
        'participations': participations, 'catalog': catalog, 'feedback_form': FeedbackForm(),
    })


@login_required
@require_POST
def request_training(request, pk):
    employee = request.user.employee_profile
    training = get_object_or_404(Training, pk=pk, is_open_for_requests=True, status=Training.Status.PLANNED)
    if employee is None:
        raise PermissionDenied
    _participant, created = TrainingParticipant.objects.get_or_create(
        training=training, employee=employee, defaults={'status': TrainingParticipant.Status.REQUESTED})
    if created:
        notify_hr(f'Demande de formation : {employee}', str(training), training.get_absolute_url())
        messages.success(request, 'Votre demande a été transmise aux RH.')
    return redirect('training:mine')


@login_required
@require_POST
def submit_feedback(request, pk):
    participant = get_object_or_404(TrainingParticipant, pk=pk, employee__user=request.user)
    form = FeedbackForm(request.POST, instance=participant)
    if form.is_valid():
        form.save()
        messages.success(request, 'Merci pour votre avis !')
    return redirect('training:mine')


@login_required
def certificate_download(request, pk):
    participant = get_object_or_404(TrainingParticipant, pk=pk)
    if not (request.user.is_hr or participant.employee.user_id == request.user.pk):
        raise PermissionDenied
    return serve_file(participant.certificate)
