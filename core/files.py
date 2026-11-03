import mimetypes
import os

from django.http import FileResponse, Http404


def serve_file(file_field, as_attachment=True):
    """Sert un fichier stocké après contrôle des droits par la vue appelante."""
    if not file_field:
        raise Http404('Fichier introuvable.')
    try:
        handle = file_field.open('rb')
    except (FileNotFoundError, OSError):
        raise Http404('Fichier introuvable.')
    filename = os.path.basename(file_field.name)
    content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    response = FileResponse(handle, as_attachment=as_attachment, filename=filename, content_type=content_type)
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, max-age=300'
    return response
