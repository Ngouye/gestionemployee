from django import template

register = template.Library()

@register.filter
def filter_status(queryset, status):
    return queryset.filter(status=status)

@register.filter
def sum_remaining_days(queryset):
    return sum(balance.remaining_days for balance in queryset)