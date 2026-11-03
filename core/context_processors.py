from django.conf import settings
from django.utils import timezone

from attendance.models import Attendance
from expenses.models import ExpenseClaim
from leaves.models import LeaveRequest

from .company import get_company


def app_context(request):
    context = {
        'company': get_company(),
        'APP_NAME': settings.APP_NAME,
        'APP_VERSION': settings.APP_VERSION,
    }
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return context

    employee = user.employee_profile
    has_team = bool(employee and employee.subordinates.exists())
    pending = 0
    if user.is_hr or has_team:
        pending = (LeaveRequest.objects.reviewable_by(user).count()
                   + ExpenseClaim.objects.reviewable_by(user).count())
    context.update({
        'current_employee': employee,
        'has_team': has_team,
        'pending_approvals_count': pending,
        'unread_notifications_count': user.notifications.filter(is_read=False).count(),
        'recent_notifications': user.notifications.all()[:6],
        'punch_record': Attendance.objects.filter(employee=employee, date=timezone.localdate()).first()
        if employee else None,
    })
    return context
