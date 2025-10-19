from django import forms
from .models import Employee


class EmployeeForm(forms.ModelForm):
	hire_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

	class Meta:
		model = Employee
		fields = ['name', 'email', 'position', 'salary', 'hire_date']