from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache

from core.forms import BootstrapFormMixin
from core.middleware import get_client_ip

User = get_user_model()


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    username = forms.EmailField(label='Adresse e-mail', widget=forms.EmailInput(attrs={
        'autofocus': True, 'autocomplete': 'email', 'placeholder': 'prenom.nom@entreprise.com'}))
    password = forms.CharField(label='Mot de passe', strip=False, widget=forms.PasswordInput(attrs={
        'autocomplete': 'current-password'}))
    remember_me = forms.BooleanField(label='Rester connecté', required=False)

    error_messages = {
        'invalid_login': 'Adresse e-mail ou mot de passe incorrect.',
        'inactive': 'Ce compte est désactivé. Contactez votre administrateur.',
    }

    def _lock_key(self):
        email = (self.data.get('username') or '').strip().lower()
        return f'login-fail:{get_client_ip(self.request)}:{email}'

    def clean(self):
        key = self._lock_key()
        attempts = cache.get(key, 0)
        if attempts >= settings.LOGIN_MAX_ATTEMPTS:
            minutes = settings.LOGIN_LOCKOUT_SECONDS // 60
            raise forms.ValidationError(
                f'Trop de tentatives de connexion. Réessayez dans {minutes} minutes.', code='locked')
        try:
            data = super().clean()
        except forms.ValidationError:
            cache.set(key, attempts + 1, settings.LOGIN_LOCKOUT_SECONDS)
            raise
        cache.delete(key)
        return data


class StyledPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    pass


class StyledPasswordResetForm(BootstrapFormMixin, PasswordResetForm):
    pass


class StyledSetPasswordForm(BootstrapFormMixin, SetPasswordForm):
    pass


class UserCreateForm(BootstrapFormMixin, forms.ModelForm):
    password1 = forms.CharField(label='Mot de passe', widget=forms.PasswordInput, required=False,
                                help_text='Laisser vide pour générer un mot de passe temporaire.')

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'role', 'is_active', 'must_change_password']

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Un utilisateur avec cette adresse existe déjà.')
        return email

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if password:
            validate_password(password)
        return password


class UserUpdateForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'role', 'is_active', 'must_change_password']

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Un utilisateur avec cette adresse existe déjà.')
        return email


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name']
