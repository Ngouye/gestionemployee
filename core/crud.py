"""Vues génériques de liste / création / modification / suppression."""
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import ProtectedError, Q
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .exports import export_response
from .utils import resolve_attr, safe_next


class CrudConfigMixin:
    title = ''
    icon = 'bi-list-ul'
    list_url_name = None
    create_url_name = None
    update_url_name = None
    delete_url_name = None
    detail_url_name = None

    def get_list_url(self):
        return reverse(self.list_url_name) if self.list_url_name else '/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': self.title,
            'page_icon': self.icon,
            'list_url': self.get_list_url(),
            'create_url_name': self.create_url_name,
            'update_url_name': self.update_url_name,
            'delete_url_name': self.delete_url_name,
            'detail_url_name': self.detail_url_name,
        })
        return context


class CrudListView(CrudConfigMixin, ListView):
    template_name = 'core/crud_list.html'
    paginate_by = 25
    columns = []          # [(libellé, attribut[, format])] format : money|date|bool|badge|color|datetime
    search_fields = []
    filters = []          # [(champ, libellé, choix ou fonction renvoyant les choix)]
    export_columns = None  # [(libellé, attribut)] : active l'export Excel/CSV
    export_filename = 'export'
    empty_message = 'Aucun élément pour le moment.'
    subtitle = ''

    def get_filters(self):
        result = []
        for name, label, choices in self.filters:
            choices = choices() if callable(choices) else choices
            result.append((name, label, [(str(value), text) for value, text in choices]))
        return result

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q', '').strip()
        if query and self.search_fields:
            condition = Q()
            for field in self.search_fields:
                condition |= Q(**{f'{field}__icontains': query})
            queryset = queryset.filter(condition)
        for name, _label, _choices in self.filters:
            value = self.request.GET.get(name)
            if value:
                queryset = queryset.filter(**{name: value})
        return queryset

    def paginate_queryset(self, queryset, page_size):
        # Les requêtes agrégées (annotate/Count) perdent le tri par défaut : on le réapplique
        # pour une pagination stable.
        if not queryset.ordered:
            queryset = queryset.order_by(*(queryset.model._meta.ordering or ['-pk']), 'pk')
        return super().paginate_queryset(queryset, page_size)

    def render_to_response(self, context, **response_kwargs):
        fmt = self.request.GET.get('export')
        if fmt in ('xlsx', 'csv') and self.export_columns:
            rows = ([resolve_attr(obj, attr) for _label, attr in self.export_columns]
                    for obj in self.get_queryset())
            return export_response(self.export_filename, [label for label, _ in self.export_columns],
                                   rows, fmt, sheet_title=self.title)
        return super().render_to_response(context, **response_kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'columns': [
                {'label': col[0], 'attr': col[1], 'fmt': col[2] if len(col) > 2 else ''}
                for col in self.columns
            ],
            'filters': [
                {'name': name, 'label': label, 'choices': choices,
                 'value': self.request.GET.get(name, '')}
                for name, label, choices in self.get_filters()
            ],
            'q': self.request.GET.get('q', ''),
            'searchable': bool(self.search_fields),
            'can_export': bool(self.export_columns),
            'empty_message': self.empty_message,
            'page_subtitle': self.subtitle,
        })
        return context


class CrudFormMixin(CrudConfigMixin, SuccessMessageMixin):
    template_name = 'core/crud_form.html'
    success_message = 'Enregistrement effectué avec succès.'
    form_title = ''

    def get_success_url(self):
        return self.get_list_url()

    def get_form_title(self):
        return self.form_title or self.title

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = self.get_form_title()
        context['cancel_url'] = safe_next(self.request, self.get_list_url())
        return context


class CrudCreateView(CrudFormMixin, CreateView):
    success_message = 'Élément créé avec succès.'


class CrudUpdateView(CrudFormMixin, UpdateView):
    success_message = 'Modifications enregistrées.'

    def get_form_title(self):
        return self.form_title or f'Modifier : {self.object}'


class CrudDeleteView(CrudConfigMixin, DeleteView):
    template_name = 'core/confirm_delete.html'

    def get_success_url(self):
        return self.get_list_url()

    def form_valid(self, form):
        label = str(self.object)
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, f'Impossible de supprimer « {label} » : '
                                         'cet élément est utilisé ailleurs dans l\'application.')
            return redirect(self.get_success_url())
        messages.success(self.request, f'« {label} » a été supprimé.')
        return response
