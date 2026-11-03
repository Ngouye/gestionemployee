"""Journal d'audit automatique sur les modèles métier."""
from datetime import date, datetime, time
from decimal import Decimal

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.fields.files import FieldFile
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .middleware import get_client_ip, get_current_request, get_current_user
from .models import AuditLog

IGNORED_FIELDS = {'updated_at', 'created_at', 'last_login', 'password'}

AUDITED_MODELS = {
    'accounts.User', 'core.CompanySettings', 'core.Announcement',
    'organization.Department', 'organization.Position',
    'employees.Employee', 'employees.Contract', 'employees.EmployeeDocument',
    'leaves.LeaveType', 'leaves.LeaveRequest', 'leaves.LeaveBalance', 'leaves.PublicHoliday',
    'attendance.Attendance', 'attendance.OvertimeType', 'attendance.OvertimeEntry',
    'payroll.PayrollRule', 'payroll.TaxBracket', 'payroll.SalaryItem', 'payroll.PayrollPeriod',
    'expenses.ExpenseClaim', 'expenses.ExpenseCategory',
    'recruitment.JobOpening', 'recruitment.Application', 'recruitment.Interview',
    'performance.ReviewCycle', 'performance.PerformanceReview', 'performance.Objective',
    'training.Training', 'training.TrainingParticipant',
}


def _is_audited(sender):
    # Les modèles « historiques » des migrations (module __fake__) ne sont jamais audités.
    return sender.__module__ != '__fake__' and sender._meta.label in AUDITED_MODELS


def _serialize(value):
    if isinstance(value, FieldFile):
        return value.name or ''
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _snapshot(instance):
    data = {}
    for field in instance._meta.concrete_fields:
        if field.name in IGNORED_FIELDS:
            continue
        data[field.name] = _serialize(getattr(instance, field.attname))
    return data


def _write(action, instance, changes=None):
    request = get_current_request()
    try:
        repr_ = str(instance)[:255]
    except Exception:
        repr_ = f'#{instance.pk}'
    AuditLog.objects.create(
        user=get_current_user(),
        action=action,
        model_name=str(instance._meta.verbose_name).capitalize(),
        object_id=str(instance.pk or ''),
        object_repr=repr_,
        changes=changes or {},
        ip_address=get_client_ip(request),
    )


@receiver(pre_save)
def audit_pre_save(sender, instance, raw=False, **kwargs):
    if raw or not _is_audited(sender) or not instance.pk:
        return
    try:
        old = sender._default_manager.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    instance._audit_before = _snapshot(old)


@receiver(post_save)
def audit_post_save(sender, instance, created, raw=False, **kwargs):
    if raw or not _is_audited(sender):
        return
    if created:
        _write(AuditLog.Action.CREATE, instance)
        return
    before = getattr(instance, '_audit_before', None)
    if before is None:
        return
    after = _snapshot(instance)
    changes = {
        key: {'avant': before.get(key), 'apres': value}
        for key, value in after.items() if before.get(key) != value
    }
    if changes:
        _write(AuditLog.Action.UPDATE, instance, changes)
    instance._audit_before = after


@receiver(post_delete)
def audit_post_delete(sender, instance, **kwargs):
    if _is_audited(sender):
        _write(AuditLog.Action.DELETE, instance)


@receiver(user_logged_in)
def audit_login(sender, request, user, **kwargs):
    AuditLog.objects.create(user=user, action=AuditLog.Action.LOGIN, model_name='Utilisateur',
                            object_id=str(user.pk), object_repr=str(user)[:255],
                            ip_address=get_client_ip(request))


@receiver(user_logged_out)
def audit_logout(sender, request, user, **kwargs):
    if user is None:
        return
    AuditLog.objects.create(user=user, action=AuditLog.Action.LOGOUT, model_name='Utilisateur',
                            object_id=str(user.pk), object_repr=str(user)[:255],
                            ip_address=get_client_ip(request))


@receiver(user_login_failed)
def audit_login_failed(sender, credentials, request=None, **kwargs):
    AuditLog.objects.create(action=AuditLog.Action.LOGIN_FAILED, model_name='Utilisateur',
                            object_repr=str(credentials.get('username', ''))[:255],
                            ip_address=get_client_ip(request))
