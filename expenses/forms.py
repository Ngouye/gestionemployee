from django import forms
from django.utils import timezone

from core.forms import BootstrapFormMixin

from .models import ExpenseCategory, ExpenseClaim


class ExpenseClaimForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ExpenseClaim
        fields = ['title', 'category', 'expense_date', 'amount', 'description', 'receipt']
        widgets = {'expense_date': forms.DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = ExpenseCategory.objects.filter(is_active=True)

    def clean(self):
        data = super().clean()
        amount, category = data.get('amount'), data.get('category')
        if amount is not None and amount <= 0:
            self.add_error('amount', 'Le montant doit être positif.')
        if amount and category and category.max_amount and amount > category.max_amount:
            self.add_error('amount', f'Montant supérieur au plafond de la catégorie ({category.max_amount:.0f}).')
        if data.get('expense_date') and data['expense_date'] > timezone.localdate():
            self.add_error('expense_date', 'La date de la dépense ne peut pas être dans le futur.')
        return data


class ExpenseDecisionForm(forms.Form):
    decision = forms.ChoiceField(choices=[('approve', 'Approuver'), ('reject', 'Refuser')])
    comment = forms.CharField(required=False)

    def clean(self):
        data = super().clean()
        if data.get('decision') == 'reject' and not data.get('comment', '').strip():
            raise forms.ValidationError('Indiquez le motif du refus.')
        return data


class ExpenseCategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ['name', 'description', 'max_amount', 'is_active']
