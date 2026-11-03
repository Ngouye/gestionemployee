from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """Oblige l'utilisateur à changer un mot de passe temporaire avant de continuer."""

    ALLOWED_PREFIXES = ('/static/', '/compte/mot-de-passe/', '/compte/deconnexion/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if (
            user is not None
            and user.is_authenticated
            and getattr(user, 'must_change_password', False)
            and not request.path.startswith(self.ALLOWED_PREFIXES)
            and not request.path.startswith('/api/')
        ):
            return redirect(reverse('accounts:password_change'))
        return self.get_response(request)
