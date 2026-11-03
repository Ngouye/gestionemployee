from datetime import time

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .validators import image_validators


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField('créé le', auto_now_add=True)
    updated_at = models.DateTimeField('modifié le', auto_now=True)

    class Meta:
        abstract = True


class CompanySettings(models.Model):
    """Paramètres de l'entreprise (instance unique)."""

    WEEKDAYS = [
        ('0', 'Lundi'), ('1', 'Mardi'), ('2', 'Mercredi'), ('3', 'Jeudi'),
        ('4', 'Vendredi'), ('5', 'Samedi'), ('6', 'Dimanche'),
    ]

    name = models.CharField('nom commercial', max_length=150, default='Mon Entreprise')
    legal_name = models.CharField('raison sociale', max_length=200, blank=True)
    logo = models.ImageField('logo', upload_to='entreprise/', blank=True, validators=image_validators)
    registration_number = models.CharField('RCCM', max_length=80, blank=True)
    tax_number = models.CharField('NINEA / identifiant fiscal', max_length=80, blank=True)
    industry = models.CharField("secteur d'activité", max_length=120, blank=True)
    address = models.CharField('adresse', max_length=255, blank=True)
    city = models.CharField('ville', max_length=100, default='Dakar')
    country = models.CharField('pays', max_length=100, default='Sénégal')
    phone = models.CharField('téléphone', max_length=30, blank=True)
    email = models.EmailField('e-mail', blank=True)
    website = models.URLField('site web', blank=True)
    currency = models.CharField('devise', max_length=10, default='FCFA')
    currency_decimals = models.PositiveSmallIntegerField(
        'décimales monétaires', default=0, choices=[(0, '0 (ex. FCFA)'), (2, '2 (ex. EUR)')],
    )
    working_days = models.CharField('jours travaillés', max_length=20, default='0,1,2,3,4')
    work_start = models.TimeField('heure de début de journée', default=time(8, 0))
    work_end = models.TimeField('heure de fin de journée', default=time(17, 0))
    late_tolerance_minutes = models.PositiveSmallIntegerField('tolérance de retard (minutes)', default=15)
    employee_id_prefix = models.CharField('préfixe des matricules', max_length=10, default='EMP')
    tax_allowance_rate = models.DecimalField(
        "abattement forfaitaire sur salaires (%)", max_digits=5, decimal_places=2, default=0,
        help_text="Déduit du revenu imposable avant application du barème (à valider avec votre comptable).")
    tax_allowance_cap = models.DecimalField("plafond annuel de l'abattement", max_digits=14, decimal_places=2,
                                            null=True, blank=True)
    hr_signatory_name = models.CharField('signataire des documents RH', max_length=150, blank=True,
                                         help_text='Nom figurant sur les attestations et certificats de travail.')
    hr_signatory_title = models.CharField('fonction du signataire', max_length=150, blank=True,
                                          default='Directeur des ressources humaines')
    updated_at = models.DateTimeField('modifié le', auto_now=True)

    class Meta:
        verbose_name = "paramètres de l'entreprise"
        verbose_name_plural = "paramètres de l'entreprise"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def working_days_list(self):
        return [int(d) for d in self.working_days.split(',') if d.strip().isdigit()]


class Notification(models.Model):
    class Level(models.TextChoices):
        INFO = 'info', 'Information'
        SUCCESS = 'success', 'Succès'
        WARNING = 'warning', 'Avertissement'
        DANGER = 'danger', 'Alerte'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='notifications', verbose_name='destinataire')
    title = models.CharField('titre', max_length=200)
    message = models.TextField('message', blank=True)
    url = models.CharField('lien', max_length=300, blank=True)
    level = models.CharField('niveau', max_length=10, choices=Level.choices, default=Level.INFO)
    is_read = models.BooleanField('lue', default=False)
    created_at = models.DateTimeField('date', auto_now_add=True)

    class Meta:
        verbose_name = 'notification'
        verbose_name_plural = 'notifications'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'is_read'])]

    def __str__(self):
        return self.title

    @property
    def icon(self):
        return {
            'info': 'bi-info-circle', 'success': 'bi-check-circle',
            'warning': 'bi-exclamation-triangle', 'danger': 'bi-x-octagon',
        }.get(self.level, 'bi-bell')


class AnnouncementQuerySet(models.QuerySet):
    def published(self):
        now = timezone.now()
        return self.filter(publish_at__lte=now).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))

    def visible_for(self, user):
        qs = self.published()
        if user.is_hr:
            return qs
        employee = user.employee_profile
        department_id = employee.department_id if employee else None
        return qs.filter(Q(department__isnull=True) | Q(department_id=department_id))


class Announcement(TimeStampedModel):
    class Category(models.TextChoices):
        GENERAL = 'GENERAL', 'Général'
        EVENT = 'EVENT', 'Événement'
        POLICY = 'POLICY', 'Politique interne'
        URGENT = 'URGENT', 'Urgent'
        CELEBRATION = 'CELEBRATION', 'Célébration'

    title = models.CharField('titre', max_length=200)
    content = models.TextField('contenu')
    category = models.CharField('catégorie', max_length=20, choices=Category.choices, default=Category.GENERAL)
    department = models.ForeignKey(
        'organization.Department', on_delete=models.CASCADE, null=True, blank=True,
        verbose_name='département ciblé', help_text="Laisser vide pour toute l'entreprise.",
    )
    is_pinned = models.BooleanField('épinglée', default=False)
    publish_at = models.DateTimeField('publiée le', default=timezone.now)
    expires_at = models.DateTimeField('expire le', null=True, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                               blank=True, verbose_name='auteur')

    objects = AnnouncementQuerySet.as_manager()

    class Meta:
        verbose_name = 'annonce'
        verbose_name_plural = 'annonces'
        ordering = ['-is_pinned', '-publish_at']

    def __str__(self):
        return self.title


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = 'CREATE', 'Création'
        UPDATE = 'UPDATE', 'Modification'
        DELETE = 'DELETE', 'Suppression'
        LOGIN = 'LOGIN', 'Connexion'
        LOGOUT = 'LOGOUT', 'Déconnexion'
        LOGIN_FAILED = 'LOGIN_FAILED', 'Échec de connexion'
        ACTION = 'ACTION', 'Action'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                             blank=True, verbose_name='utilisateur')
    action = models.CharField('action', max_length=20, choices=Action.choices)
    model_name = models.CharField('objet', max_length=100, blank=True)
    object_id = models.CharField('identifiant', max_length=64, blank=True)
    object_repr = models.CharField('description', max_length=255, blank=True)
    changes = models.JSONField('modifications', default=dict, blank=True)
    ip_address = models.GenericIPAddressField('adresse IP', null=True, blank=True)
    created_at = models.DateTimeField('date', auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "entrée du journal d'audit"
        verbose_name_plural = "journal d'audit"
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_action_display()} — {self.object_repr}'
