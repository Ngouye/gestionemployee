import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

from .middleware import get_client_ip, get_current_request, get_current_user
from .models import AuditLog, Notification

logger = logging.getLogger(__name__)


def notify(user, title, message='', url='', level=Notification.Level.INFO, email=True):
    """Crée une notification interne et, si configuré, envoie un e-mail."""
    if user is None or not user.is_active:
        return None
    notification = Notification.objects.create(
        user=user, title=title[:200], message=message, url=url, level=level,
    )
    if email and settings.EMAIL_NOTIFICATIONS and user.email:
        body = message
        if url:
            request = get_current_request()
            link = request.build_absolute_uri(url) if request else url
            body = f'{message}\n\n{link}'
        try:
            send_mail(title, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
        except Exception:  # pragma: no cover - ne jamais bloquer le métier pour un e-mail
            logger.exception("Échec d'envoi de l'e-mail de notification")
    return notification


def notify_users(users, title, message='', url='', level=Notification.Level.INFO):
    for user in users:
        notify(user, title, message, url, level)


def hr_users():
    User = get_user_model()
    return User.objects.filter(is_active=True, role__in=[User.Role.HR, User.Role.ADMIN])


def notify_hr(title, message='', url='', level=Notification.Level.INFO, exclude=None):
    for user in hr_users():
        if exclude is not None and user.pk == exclude.pk:
            continue
        notify(user, title, message, url, level)


def log_action(action, obj=None, description='', changes=None, user=None):
    """Ajoute une entrée explicite au journal d'audit."""
    request = get_current_request()
    AuditLog.objects.create(
        user=user or get_current_user(),
        action=action,
        model_name=obj._meta.verbose_name.capitalize() if obj is not None else '',
        object_id=str(obj.pk) if obj is not None and obj.pk else '',
        object_repr=(description or str(obj or ''))[:255],
        changes=changes or {},
        ip_address=get_client_ip(request),
    )
