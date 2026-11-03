from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import ListView, UpdateView

from attendance.models import Attendance
from expenses.models import ExpenseClaim
from leaves.models import LeaveRequest
from leaves.services import balances_for
from payroll.models import PayrollPeriod, Payslip
from performance.models import Objective, PerformanceReview
from recruitment.models import Interview

from .company import get_company
from .crud import CrudCreateView, CrudDeleteView, CrudListView, CrudUpdateView
from .dashboard import hr_dashboard
from .files import serve_file
from .forms import AnnouncementForm, CompanySettingsForm
from .models import Announcement, AuditLog, CompanySettings, Notification
from .permissions import AdminRequiredMixin, HRRequiredMixin
from .utils import safe_next


@login_required
def dashboard(request):
    user = request.user
    today = timezone.localdate()
    employee = user.employee_profile
    context = {
        'today': today,
        'announcements': Announcement.objects.visible_for(user).select_related('author')[:5],
        'pending_leaves': LeaveRequest.objects.reviewable_by(user).select_related('employee', 'leave_type')[:6],
        'pending_expenses': ExpenseClaim.objects.reviewable_by(user).select_related('employee', 'category')[:6],
        'upcoming_interviews': Interview.objects.filter(
            interviewer=user, status=Interview.Status.SCHEDULED, scheduled_at__gte=timezone.now()
        ).select_related('application__job')[:5],
        'reviews_to_do': PerformanceReview.objects.filter(
            reviewer=user, status=PerformanceReview.Status.PENDING).select_related('employee', 'cycle')[:5],
    }
    if employee:
        context.update({
            'balances': balances_for(employee, today.year),
            'today_attendance': Attendance.objects.filter(employee=employee, date=today).first(),
            'my_requests': employee.leave_requests.select_related('leave_type')[:5],
            'my_objectives': employee.objectives.exclude(
                status__in=[Objective.Status.ACHIEVED, Objective.Status.MISSED])[:5],
            'last_payslip': Payslip.objects.filter(employee=employee).exclude(
                period__status=PayrollPeriod.Status.DRAFT).select_related('period').first(),
            'team_size': employee.subordinates.filter(status='ACTIVE').count(),
        })
    if user.is_hr:
        context.update(hr_dashboard(today))
    return render(request, 'core/dashboard.html', context)


@login_required
def approvals(request):
    user = request.user
    return render(request, 'core/approvals.html', {
        'leaves': LeaveRequest.objects.reviewable_by(user).select_related('employee__department', 'leave_type'),
        'expenses': ExpenseClaim.objects.reviewable_by(user).select_related('employee', 'category'),
    })


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class NotificationListView(LoginRequiredMixin, ListView):
    template_name = 'core/notifications.html'
    context_object_name = 'notifications'
    paginate_by = 30

    def get_queryset(self):
        return self.request.user.notifications.all()


@login_required
def notification_open(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])
    url = notification.url
    if url and url.startswith('/') and not url.startswith('//'):
        return redirect(url)
    return redirect('core:notifications')


@login_required
@require_POST
def notifications_mark_all(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    messages.success(request, 'Toutes les notifications ont été marquées comme lues.')
    return redirect(safe_next(request, reverse('core:notifications')))


# ---------------------------------------------------------------------------
# Annonces
# ---------------------------------------------------------------------------

class AnnouncementFeedView(LoginRequiredMixin, ListView):
    template_name = 'core/announcements.html'
    context_object_name = 'announcements'
    paginate_by = 10

    def get_queryset(self):
        return Announcement.objects.visible_for(self.request.user).select_related('author', 'department')


class AnnouncementConfig(HRRequiredMixin):
    model = Announcement
    form_class = AnnouncementForm
    title = 'Gestion des annonces'
    icon = 'bi-megaphone'
    list_url_name = 'core:announcement_admin'
    create_url_name = 'core:announcement_create'
    update_url_name = 'core:announcement_update'
    delete_url_name = 'core:announcement_delete'


class AnnouncementAdminListView(AnnouncementConfig, CrudListView):
    columns = [('Titre', 'title'), ('Catégorie', 'category', 'badge'), ('Cible', 'department'),
               ('Publiée le', 'publish_at'), ('Expire le', 'expires_at'), ('Épinglée', 'is_pinned', 'bool')]
    search_fields = ['title', 'content']
    filters = [('category', 'Catégorie', Announcement.Category.choices)]


class AnnouncementCreateView(AnnouncementConfig, CrudCreateView):
    form_title = 'Nouvelle annonce'

    def get_initial(self):
        return {'publish_at': timezone.localtime().replace(second=0, microsecond=0)}

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)


class AnnouncementUpdateView(AnnouncementConfig, CrudUpdateView):
    pass


class AnnouncementDeleteView(AnnouncementConfig, CrudDeleteView):
    pass


# ---------------------------------------------------------------------------
# Administration
# ---------------------------------------------------------------------------

class CompanySettingsView(AdminRequiredMixin, UpdateView):
    form_class = CompanySettingsForm
    template_name = 'core/settings.html'

    def get_object(self, queryset=None):
        return CompanySettings.load()

    def form_valid(self, form):
        messages.success(self.request, 'Paramètres enregistrés.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('core:settings')


class AuditLogView(AdminRequiredMixin, CrudListView):
    model = AuditLog
    template_name = 'core/audit_log.html'
    title = "Journal d'audit"
    icon = 'bi-shield-check'
    list_url_name = 'core:audit_log'
    paginate_by = 50
    search_fields = ['object_repr', 'model_name', 'user__email', 'ip_address']
    filters = [
        ('action', 'Action', AuditLog.Action.choices),
        ('user', 'Utilisateur', lambda: get_user_model().objects.values_list('pk', 'email')),
    ]
    export_columns = [('Date', 'created_at'), ('Utilisateur', 'user'), ('Action', 'get_action_display'),
                      ('Objet', 'model_name'), ('Description', 'object_repr'), ('Adresse IP', 'ip_address'),
                      ('Modifications', 'changes')]
    export_filename = 'journal_audit'

    def get_queryset(self):
        return super().get_queryset().select_related('user')


def company_logo(request):
    return serve_file(get_company().logo, as_attachment=False)


def health(request):
    """Point de contrôle pour Docker et la supervision."""
    try:
        connection.ensure_connection()
    except DatabaseError:
        return JsonResponse({'status': 'erreur', 'database': False}, status=503)
    return JsonResponse({'status': 'ok', 'database': True, 'version': settings.APP_VERSION})


# ---------------------------------------------------------------------------
# Pages d'erreur
# ---------------------------------------------------------------------------

def error_403(request, exception=None):
    return render(request, 'errors/403.html', status=403)


def error_404(request, exception=None):
    return render(request, 'errors/404.html', status=404)


def error_500(request):
    return render(request, 'errors/500.html', status=500)
