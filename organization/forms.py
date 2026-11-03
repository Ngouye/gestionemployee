from django import forms

from core.forms import BootstrapFormMixin

from .models import Department, Position


class DepartmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'code', 'parent', 'head', 'description', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['head'].queryset = self.fields['head'].queryset.filter(status='ACTIVE')
        if self.instance.pk:
            self.fields['parent'].queryset = Department.objects.exclude(pk=self.instance.pk)

    def clean_parent(self):
        parent = self.cleaned_data.get('parent')
        node = parent
        while node is not None and self.instance.pk:
            if node.pk == self.instance.pk:
                raise forms.ValidationError('Un département ne peut pas dépendre de lui-même.')
            node = node.parent
        return parent


class PositionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Position
        fields = ['title', 'department', 'grade', 'is_executive', 'min_salary', 'max_salary', 'description',
                  'is_active']

    def clean(self):
        data = super().clean()
        low, high = data.get('min_salary'), data.get('max_salary')
        if low is not None and high is not None and low > high:
            self.add_error('max_salary', 'Le salaire maximum doit être supérieur au minimum.')
        return data
