import threading

_local = threading.local()


def get_current_request():
    return getattr(_local, 'request', None)


def get_current_user():
    request = get_current_request()
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        return user
    return None


def get_client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip() or None
    return request.META.get('REMOTE_ADDR') or None


class CurrentUserMiddleware:
    """Mémorise la requête courante pour le journal d'audit."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _local.request = request
        try:
            return self.get_response(request)
        finally:
            _local.request = None
