from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from rest_framework.authtoken.models import Token

from core.crud import CrudCreateView, CrudListView, CrudUpdateView
from core.permissions import AdminRequiredMixin, is_admin, role_required

from .forms import (LoginForm, ProfileForm, StyledPasswordChangeForm, StyledPasswordResetForm,
                    StyledSetPasswordForm, UserCreateForm, UserUpdateForm)
from .services import generate_temporary_password

User = get_user_model()


class LoginView(auth_views.LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        if not form.cleaned_data.get('remember_me'):
            self.request.session.set_expiry(0)
        response = super().form_valid(form)
        messages.success(self.request, f'Bienvenue, {self.request.user.first_name or self.request.user.email} !')
        return response


class LogoutView(auth_views.LogoutView):
    next_page = reverse_lazy('accounts:login')


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = 'accounts/password_change.html'
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy('core:dashboard')

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.user.must_change_password:
            self.request.user.must_change_password = False
            self.request.user.save(update_fields=['must_change_password'])
        messages.success(self.request, 'Votre mot de passe a été modifié.')
        return response


class PasswordResetView(auth_views.PasswordResetView):
    template_name = 'accounts/password_reset.html'
    form_class = StyledPasswordResetForm
    email_template_name = 'accounts/emails/password_reset_email.txt'
    subject_template_name = 'accounts/emails/password_reset_subject.txt'
    success_url = reverse_lazy('accounts:password_reset_done')


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    form_class = StyledSetPasswordForm
    success_url = reverse_lazy('accounts:password_reset_complete')

    def form_valid(self, form):
        response = super().form_valid(form)
        form.user.must_change_password = False
        form.user.save(update_fields=['must_change_password'])
        return response


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profil mis à jour.')
        return redirect('accounts:profile')
    token = Token.objects.filter(user=request.user).first()
    return render(request, 'accounts/profile.html', {'form': form, 'api_token': token})


@login_required
@require_POST
def api_token(request):
    Token.objects.filter(user=request.user).delete()
    token = Token.objects.create(user=request.user)
    messages.success(request, f'Nouveau jeton API généré : {token.key}')
    return redirect('accounts:profile')


# ---------------------------------------------------------------------------
# Gestion des utilisateurs (administrateurs)
# ---------------------------------------------------------------------------

class UserConfig(AdminRequiredMixin):
    model = User
    title = 'Utilisateurs'
    icon = 'bi-person-gear'
    list_url_name = 'accounts:user_list'
    create_url_name = 'accounts:user_create'
    update_url_name = 'accounts:user_update'


class UserListView(UserConfig, CrudListView):
    columns = [('Nom', 'display_name'), ('E-mail', 'email'), ('Rôle', 'role', 'badge'),
               ('Fiche employé', 'employee_profile'), ('Dernière connexion', 'last_login'),
               ('Actif', 'is_active', 'bool')]
    search_fields = ['email', 'first_name', 'last_name']
    filters = [('role', 'Rôle', User.Role.choices), ('is_active', 'Actif', [('1', 'Oui'), ('0', 'Non')])]
    export_columns = [('E-mail', 'email'), ('Prénom', 'first_name'), ('Nom', 'last_name'),
                      ('Rôle', 'get_role_display'), ('Actif', 'is_active'), ('Dernière connexion', 'last_login')]
    export_filename = 'utilisateurs'

    def get_queryset(self):
        return super().get_queryset().select_related('employee')


class UserCreateView(UserConfig, CrudCreateView):
    form_class = UserCreateForm
    form_title = 'Nouvel utilisateur'

    def form_valid(self, form):
        password = form.cleaned_data.get('password1') or generate_temporary_password()
        user = form.save(commit=False)
        user.set_password(password)
        if not form.cleaned_data.get('password1'):
            user.must_change_password = True
        user.save()
        self.object = user
        messages.success(self.request, f'Utilisateur {user.email} créé.')
        if not form.cleaned_data.get('password1'):
            messages.info(self.request, f'Mot de passe temporaire : {password}')
        return redirect(self.get_success_url())


class UserUpdateView(UserConfig, CrudUpdateView):
    form_class = UserUpdateForm

    def form_valid(self, form):
        if form.instance.pk == self.request.user.pk and not form.cleaned_data.get('is_active'):
            form.add_error('is_active', 'Vous ne pouvez pas désactiver votre propre compte.')
            return self.form_invalid(form)
        return super().form_valid(form)


@role_required(is_admin)
@require_POST
def user_reset_password(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.is_superuser and not request.user.is_superuser:
        raise PermissionDenied
    password = generate_temporary_password()
    user.set_password(password)
    user.must_change_password = True
    user.save()
    messages.success(request, f'Nouveau mot de passe temporaire pour {user.email} : {password}')
    return redirect('accounts:user_update', pk=pk)
