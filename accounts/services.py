import secrets
import string

from django.contrib.auth import get_user_model


def generate_temporary_password(length=12):
    alphabet = string.ascii_letters + string.digits
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length - 2))
        password += secrets.choice('@#$%&*!?') + secrets.choice(string.digits)
        if any(c.islower() for c in password) and any(c.isupper() for c in password):
            return password


def create_account_for_employee(employee, role):
    """Crée (ou réactive) le compte d'accès d'un employé. Renvoie (user, mot_de_passe_temporaire)."""
    User = get_user_model()
    password = generate_temporary_password()
    user = employee.user or User.objects.filter(email__iexact=employee.email).first()
    if user is None:
        user = User.objects.create_user(
            email=employee.email, password=password, first_name=employee.first_name,
            last_name=employee.last_name, role=role, must_change_password=True,
        )
    else:
        linked = user.employee_profile
        if linked is not None and linked.pk != employee.pk:
            raise ValueError(f'Le compte {user.email} est déjà rattaché à {linked}.')
        user.set_password(password)
        user.role = role
        user.is_active = True
        user.must_change_password = True
        user.save()
    if employee.user_id != user.pk:
        employee.user = user
        employee.save(update_fields=['user'])
    return user, password
