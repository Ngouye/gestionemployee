from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def is_hr(user):
    return user.is_authenticated and user.is_hr


def is_admin(user):
    return user.is_authenticated and user.is_admin_role


def has_team(user):
    employee = user.employee_profile if user.is_authenticated else None
    return bool(employee and employee.subordinates.exists())


def is_hr_or_manager(user):
    return is_hr(user) or has_team(user)


class HRRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Réservé aux ressources humaines et administrateurs."""

    def test_func(self):
        return is_hr(self.request.user)


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_admin(self.request.user)


class ManagerOrHRRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_hr_or_manager(self.request.user)


class EmployeeRequiredMixin(LoginRequiredMixin):
    """Exige une fiche employé liée au compte connecté (espace personnel)."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.employee_profile is None:
            messages.warning(request, "Votre compte n'est lié à aucune fiche employé. "
                                      "Contactez les ressources humaines.")
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)

    @property
    def employee(self):
        return self.request.user.employee_profile


def role_required(check):
    """Décorateur de vue fonction : `@role_required(is_hr)`."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(request, *args, **kwargs):
            if not check(request.user):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
