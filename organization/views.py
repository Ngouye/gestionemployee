from django.db.models import Count, Q

from core.crud import CrudCreateView, CrudDeleteView, CrudListView, CrudUpdateView
from core.permissions import HRRequiredMixin

from .forms import DepartmentForm, PositionForm
from .models import Department, Position


class DepartmentConfig:
    model = Department
    title = 'Départements'
    icon = 'bi-diagram-3'
    list_url_name = 'organization:department_list'
    create_url_name = 'organization:department_create'
    update_url_name = 'organization:department_update'
    delete_url_name = 'organization:department_delete'


class DepartmentListView(HRRequiredMixin, DepartmentConfig, CrudListView):
    columns = [('Nom', 'name'), ('Code', 'code'), ('Responsable', 'head'),
               ('Département parent', 'parent'), ('Effectif actif', 'headcount'),
               ('Actif', 'is_active', 'bool')]
    search_fields = ['name', 'code']
    export_columns = [('Nom', 'name'), ('Code', 'code'), ('Responsable', 'head'),
                      ('Parent', 'parent'), ('Effectif actif', 'headcount')]
    export_filename = 'departements'

    def get_queryset(self):
        return super().get_queryset().select_related('head', 'parent').annotate(
            headcount=Count('employees', filter=Q(employees__status='ACTIVE')))


class DepartmentCreateView(HRRequiredMixin, DepartmentConfig, CrudCreateView):
    form_class = DepartmentForm
    form_title = 'Nouveau département'


class DepartmentUpdateView(HRRequiredMixin, DepartmentConfig, CrudUpdateView):
    form_class = DepartmentForm


class DepartmentDeleteView(HRRequiredMixin, DepartmentConfig, CrudDeleteView):
    pass


class PositionConfig:
    model = Position
    title = 'Postes'
    icon = 'bi-briefcase'
    list_url_name = 'organization:position_list'
    create_url_name = 'organization:position_create'
    update_url_name = 'organization:position_update'
    delete_url_name = 'organization:position_delete'


class PositionListView(HRRequiredMixin, PositionConfig, CrudListView):
    columns = [('Intitulé', 'title'), ('Département', 'department'), ('Grade', 'grade'),
               ('Cadre', 'is_executive', 'bool'), ('Salaire min.', 'min_salary', 'money'),
               ('Salaire max.', 'max_salary', 'money'), ('Titulaires', 'holders'), ('Actif', 'is_active', 'bool')]
    search_fields = ['title', 'grade', 'department__name']
    filters = [('department', 'Département',
                lambda: Department.objects.values_list('pk', 'name'))]
    export_columns = [('Intitulé', 'title'), ('Département', 'department'), ('Grade', 'grade'),
                      ('Salaire min.', 'min_salary'), ('Salaire max.', 'max_salary')]
    export_filename = 'postes'

    def get_queryset(self):
        return super().get_queryset().select_related('department').annotate(
            holders=Count('employees', filter=Q(employees__status='ACTIVE')))


class PositionCreateView(HRRequiredMixin, PositionConfig, CrudCreateView):
    form_class = PositionForm
    form_title = 'Nouveau poste'


class PositionUpdateView(HRRequiredMixin, PositionConfig, CrudUpdateView):
    form_class = PositionForm


class PositionDeleteView(HRRequiredMixin, PositionConfig, CrudDeleteView):
    pass
