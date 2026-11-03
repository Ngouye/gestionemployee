from django.db import models

from core.models import TimeStampedModel


class Department(TimeStampedModel):
    name = models.CharField('nom', max_length=120, unique=True)
    code = models.CharField('code', max_length=20, blank=True)
    description = models.TextField('description', blank=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='children', verbose_name='département parent')
    head = models.ForeignKey('employees.Employee', on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='headed_departments', verbose_name='responsable')
    is_active = models.BooleanField('actif', default=True)

    class Meta:
        verbose_name = 'département'
        verbose_name_plural = 'départements'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def active_headcount(self):
        return self.employees.filter(status='ACTIVE').count()


class Position(TimeStampedModel):
    title = models.CharField('intitulé du poste', max_length=150)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='positions', verbose_name='département')
    grade = models.CharField('catégorie / grade', max_length=80, blank=True,
                             help_text='Ex. : Cadre, Agent de maîtrise, Employé, Ouvrier.')
    description = models.TextField('description / missions', blank=True)
    min_salary = models.DecimalField('salaire minimum', max_digits=12, decimal_places=2, null=True, blank=True)
    max_salary = models.DecimalField('salaire maximum', max_digits=12, decimal_places=2, null=True, blank=True)
    is_executive = models.BooleanField('poste cadre', default=False,
                                       help_text='Détermine les cotisations réservées aux cadres (ex. IPRES cadre).')
    is_active = models.BooleanField('actif', default=True)

    class Meta:
        verbose_name = 'poste'
        verbose_name_plural = 'postes'
        ordering = ['title']
        constraints = [
            models.UniqueConstraint(fields=['title', 'department'], name='unique_position_per_department'),
        ]

    def __str__(self):
        return self.title
