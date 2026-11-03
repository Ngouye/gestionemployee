from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.deconstruct import deconstructible

DOCUMENT_EXTENSIONS = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'odt', 'ods', 'png', 'jpg', 'jpeg', 'txt']
IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'webp']


@deconstructible
class MaxFileSizeValidator:
    def __init__(self, max_mb=None):
        self.max_mb = max_mb

    def __call__(self, value):
        limit = self.max_mb or getattr(settings, 'MAX_UPLOAD_SIZE_MB', 10)
        if value and getattr(value, 'size', 0) > limit * 1024 * 1024:
            raise ValidationError(f'Le fichier dépasse la taille maximale autorisée ({limit} Mo).')

    def __eq__(self, other):
        return isinstance(other, MaxFileSizeValidator) and self.max_mb == other.max_mb


document_validators = [FileExtensionValidator(DOCUMENT_EXTENSIONS), MaxFileSizeValidator()]
image_validators = [FileExtensionValidator(IMAGE_EXTENSIONS), MaxFileSizeValidator(5)]
