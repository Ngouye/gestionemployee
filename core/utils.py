import calendar
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import models
from django.utils.http import url_has_allowed_host_and_scheme


def resolve_attr(obj, path):
    """Résout un chemin d'attribut pointé (`department.name`), en appelant les méthodes."""
    value = obj
    for part in path.split('.'):
        if value is None:
            return None
        value = getattr(value, part, None)
        if callable(value) and not isinstance(value, models.Manager):
            value = value()
    return value


def format_money(value, decimals=0, currency='', separator=' '):
    if value in (None, ''):
        return '—'
    try:
        amount = Decimal(value)
    except Exception:
        return str(value)
    quant = Decimal(1) if decimals == 0 else Decimal(1).scaleb(-decimals)
    amount = amount.quantize(quant, rounding=ROUND_HALF_UP)
    sign = '-' if amount < 0 else ''
    integer, _, fraction = f'{abs(amount):f}'.partition('.')
    groups = []
    while integer:
        groups.insert(0, integer[-3:])
        integer = integer[:-3]
    text = separator.join(groups) or '0'
    if decimals:
        text = f'{text},{fraction.ljust(decimals, "0")[:decimals]}'
    return f'{sign}{text} {currency}'.strip()


def month_bounds(year, month):
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


MONTHS_FR = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
             'septembre', 'octobre', 'novembre', 'décembre']


def month_label(year, month):
    return f'{MONTHS_FR[month - 1].capitalize()} {year}'


def safe_next(request, default):
    """Cible de redirection `next` validée (même hôte uniquement), sinon `default`."""
    target = request.POST.get('next') or request.GET.get('next')
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                                  require_https=request.is_secure()):
        return target
    return default
