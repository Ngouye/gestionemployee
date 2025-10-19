from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import logout  # Import pour la déconnexion
from django.db.models import Sum, Q  # Imports pour l'agrégation et le filtrage
from django.http import HttpResponseForbidden

from .models import Employee
from .forms import EmployeeForm

# ----------------------------------------------------------------------
# VUES CRUD ET TABLEAU DE BORD
# ----------------------------------------------------------------------

@login_required
def employee_list(request):
    # Vérifie la permission de visualisation (autorise le staff par défaut)
    if not (request.user.is_staff or request.user.has_perm('employees.view_employee')):
        messages.error(request, "Vous n'avez pas la permission de voir la liste des employés.")
        return redirect('login')

    employees = Employee.objects.all().order_by('name')
    query = request.GET.get('q')  # Récupère la requête de recherche

    # --- Logique de Filtrage ---
    if query:
        # Filtre les employés par Nom, Email ou Poste (insensible à la casse)
        employees = employees.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(position__icontains=query)
        ).distinct()

    # --- Calcul de la Masse Salariale (Agrégation) ---
    total_payroll = employees.aggregate(total=Sum('salary'))['total']
    if total_payroll is None:
        total_payroll = 0

    context = {
        'employees': employees,
        'query': query,
        'total_payroll': total_payroll,
    }
    return render(request, 'employees/employee_list.html', context)


@login_required
def employee_create(request):
    # Permission d'ajout
    if not (request.user.is_staff or request.user.has_perm('employees.add_employee')):
        messages.error(request, "Vous n'avez pas la permission de créer un employé.")
        return redirect('employee_list')

    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Employé ajouté avec succès !')
            return redirect('employee_list')
        else:
            messages.error(request, 'Veuillez corriger les erreurs du formulaire.')
    else:
        form = EmployeeForm()
    return render(request, 'employees/employee_form.html', {'form': form})


@login_required
def employee_update(request, pk):
    employee = get_object_or_404(Employee, pk=pk)

    # Permission de modification
    if not (request.user.is_staff or request.user.has_perm('employees.change_employee')):
        messages.error(request, "Vous n'avez pas la permission de modifier cet employé.")
        return redirect('employee_list')

    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, f'Employé {employee.name} modifié avec succès !')
            return redirect('employee_list')
        else:
            messages.error(request, 'Veuillez corriger les erreurs du formulaire.')
    else:
        form = EmployeeForm(instance=employee)
    return render(request, 'employees/employee_form.html', {'form': form, 'employee': employee})


@login_required
def employee_delete(request, pk):
    employee = get_object_or_404(Employee, pk=pk)

    # Permission de suppression
    if not (request.user.is_staff or request.user.has_perm('employees.delete_employee')):
        messages.error(request, "Vous n'avez pas la permission de supprimer cet employé.")
        return redirect('employee_list')

    if request.method == 'POST':
        employee_name = employee.name  # Sauvegarde le nom avant suppression
        employee.delete()
        messages.success(request, f'Employé {employee_name} supprimé avec succès !')
        return redirect('employee_list')

    # Passe la variable 'object' pour compatibilité avec employee_confirm_delete.html
    return render(request, 'employees/employee_confirm_delete.html', {'employee': employee, 'object': employee})


# ----------------------------------------------------------------------
# VUE AUTHENTIFICATION
# ----------------------------------------------------------------------

def custom_logout_view(request):
    """Déconnecte l'utilisateur et affiche un message de succès."""
    logout(request)
    messages.info(request, "Vous avez été déconnecté avec succès.")
    return redirect('login')