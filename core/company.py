from .middleware import get_current_request
from .models import CompanySettings


def get_company():
    """Paramètres de l'entreprise, mémorisés pour la durée de la requête."""
    request = get_current_request()
    if request is None:
        return CompanySettings.load()
    company = getattr(request, '_company_settings', None)
    if company is None:
        company = CompanySettings.load()
        request._company_settings = company
    return company
