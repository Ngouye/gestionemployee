from datetime import date, datetime
from decimal import Decimal

from django import template
from django.utils import timezone
from django.utils.dateformat import format as date_format
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import mark_safe

from core.company import get_company
from core.utils import format_money, resolve_attr
from employees.access import can_view_employee

register = template.Library()

BADGE_COLORS = {
    'success': {'APPROVED', 'VALIDATED', 'ACTIVE', 'OPEN', 'HIRED', 'PRESENT', 'COMPLETED',
                'ACHIEVED', 'DONE', 'ATTENDED', 'PASSED', 'CREATE', 'LOGIN', 'ALLOWANCE'},
    'warning': {'PENDING', 'SUBMITTED', 'LATE', 'OFFER', 'SUSPENDED', 'TRIAL', 'HALF_DAY', 'REQUESTED',
                'POLICY', 'HR', 'DEDUCTION'},
    'danger': {'REJECTED', 'TERMINATED', 'ABSENT', 'MISSED', 'FAILED', 'URGENT', 'DELETE', 'LOGIN_FAILED',
               'ADMIN'},
    'primary': {'PAID', 'INTERVIEW', 'ONGOING', 'IN_PROGRESS', 'IN_REVIEW', 'UPDATE', 'MANAGER', 'ACTION'},
    'info': {'NEW', 'SCREENING', 'REMOTE', 'PLANNED', 'SCHEDULED', 'REGISTERED', 'ON_LEAVE',
             'EVENT', 'CELEBRATION', 'GENERAL'},
}


def _badge_color(code):
    code = str(code or '').upper()
    for color, codes in BADGE_COLORS.items():
        if code in codes:
            return color
    return 'secondary'


@register.filter
def money(value, with_currency=True):
    company = get_company()
    return format_money(value, company.currency_decimals, company.currency if with_currency else '')


@register.filter
def days(value):
    if value in (None, ''):
        return '—'
    value = Decimal(value).normalize()
    text = f'{value:f}'.replace('.', ',')
    return f'{text} j'


@register.filter
def status_badge(code, label=None):
    color = _badge_color(code)
    return format_html(
        '<span class="badge rounded-pill bg-{0}-subtle text-{0}-emphasis border border-{0}-subtle">{1}</span>',
        color, label or code or '—',
    )


@register.filter
def initials(value):
    parts = [p for p in str(value or '').replace('-', ' ').split() if p]
    return ''.join(p[0] for p in parts[:2]).upper() or '?'


@register.filter
def field(form, name):
    return form[name]


@register.filter
def can_view(user, employee):
    """`{% if user|can_view:employee %}` : l'utilisateur peut-il ouvrir la fiche ?"""
    return bool(employee) and user.is_authenticated and can_view_employee(user, employee)


@register.filter
def getitem(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def percent(value, total):
    try:
        return round(float(value) * 100 / float(total)) if float(total) else 0
    except (TypeError, ValueError):
        return 0


@register.simple_tag(takes_context=True)
def nav_active(context, *prefixes):
    request = context.get('request')
    path = request.path if request else ''
    for prefix in prefixes:
        if prefix == '/' and path == '/':
            return 'active'
        if prefix != '/' and path.startswith(prefix):
            return 'active'
    return ''


def _bool_icon(value):
    if value:
        return mark_safe('<i class="bi bi-check-circle-fill text-success" title="Oui"></i>')
    return mark_safe('<i class="bi bi-dash-circle text-body-tertiary" title="Non"></i>')


def _badge_cell(obj, attr, value):
    display = getattr(obj, f'get_{attr}_display', None)
    return status_badge(value, display() if callable(display) else value)


def _progress_cell(value):
    return format_html(
        '<div class="progress" style="height:6px;min-width:80px" role="progressbar" aria-label="Avancement" '
        'aria-valuenow="{0}" aria-valuemin="0" aria-valuemax="100">'
        '<div class="progress-bar" style="width:{0}%"></div></div><small class="text-body-secondary">{0}%</small>',
        int(value or 0),
    )


CELL_FORMATTERS = {
    'badge': _badge_cell,
    'money': lambda obj, attr, value: money(value),
    'days': lambda obj, attr, value: days(value),
    'color': lambda obj, attr, value: format_html(
        '<span class="color-swatch" style="background:{}"></span>', value or '#999'),
    'progress': lambda obj, attr, value: _progress_cell(value),
    'bool': lambda obj, attr, value: _bool_icon(value),
}


def _plain_cell(value):
    if isinstance(value, bool):
        return _bool_icon(value)
    if value is None or value == '':
        return mark_safe('<span class="text-body-tertiary">—</span>')
    if isinstance(value, datetime):
        return date_format(timezone.localtime(value) if timezone.is_aware(value) else value, 'd/m/Y H:i')
    if isinstance(value, date):
        return date_format(value, 'd/m/Y')
    if isinstance(value, Decimal):
        return f'{value.normalize():f}'.replace('.', ',')
    return conditional_escape(value)


@register.simple_tag
def cell(obj, column):
    """Rendu d'une cellule de tableau générique selon son format (`money`, `badge`, `bool`…)."""
    attr = column['attr']
    value = resolve_attr(obj, attr)
    formatter = CELL_FORMATTERS.get(column['fmt'])
    return formatter(obj, attr, value) if formatter else _plain_cell(value)
