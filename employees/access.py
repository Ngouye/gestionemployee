def can_view_employee(user, employee):
    """RH : tous les employés ; manager : son équipe directe ; employé : lui-même."""
    if user.is_hr:
        return True
    own = user.employee_profile
    return own is not None and (own.pk == employee.pk or employee.manager_id == own.pk)
