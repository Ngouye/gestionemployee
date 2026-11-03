from rest_framework import serializers

from attendance.models import Attendance
from employees.models import Employee
from leaves import services as leave_services
from leaves.models import LeaveRequest, LeaveType
from organization.models import Department, Position


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'code', 'description', 'parent', 'head', 'is_active']


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ['id', 'title', 'department', 'grade', 'description', 'is_active']


class EmployeePublicSerializer(serializers.ModelSerializer):
    """Informations d'annuaire, visibles par tous les collaborateurs."""

    department_name = serializers.CharField(source='department.name', read_only=True, default=None)
    position_title = serializers.CharField(source='position.title', read_only=True, default=None)

    class Meta:
        model = Employee
        fields = ['id', 'employee_id', 'first_name', 'last_name', 'email', 'phone', 'department',
                  'department_name', 'position', 'position_title', 'manager', 'status']
        read_only_fields = fields


class EmployeeSerializer(serializers.ModelSerializer):
    """Fiche complète (ressources humaines)."""

    department_name = serializers.CharField(source='department.name', read_only=True, default=None)
    position_title = serializers.CharField(source='position.title', read_only=True, default=None)
    base_salary = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Employee
        exclude = ['photo', 'user', 'notes']
        read_only_fields = ['employee_id', 'created_at', 'updated_at']


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ['id', 'name', 'code', 'color', 'annual_allowance', 'tracks_balance', 'is_paid',
                  'requires_attachment']


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)

    class Meta:
        model = LeaveRequest
        fields = ['id', 'employee', 'employee_name', 'leave_type', 'leave_type_name', 'start_date', 'end_date',
                  'half_day', 'days', 'reason', 'status', 'reviewed_by', 'reviewed_at', 'review_comment',
                  'created_at']
        read_only_fields = ['employee', 'days', 'status', 'reviewed_by', 'reviewed_at', 'review_comment',
                            'created_at']

    def validate(self, attrs):
        employee = self.context['request'].user.employee_profile
        if employee is None:
            raise serializers.ValidationError('Aucune fiche employé liée à ce compte.')
        start, end = attrs['start_date'], attrs['end_date']
        if end < start:
            raise serializers.ValidationError({'end_date': 'La date de fin doit suivre la date de début.'})
        days = leave_services.working_days(start, end, attrs.get('half_day', False))
        if days <= 0:
            raise serializers.ValidationError('La période ne contient aucun jour ouvré.')
        if leave_services.overlapping_requests(employee, start, end).exists():
            raise serializers.ValidationError('Une demande existe déjà sur cette période.')
        leave_type = attrs['leave_type']
        if leave_type.requires_attachment:
            raise serializers.ValidationError('Ce type de congé nécessite un justificatif : utilisez l’application web.')
        if leave_type.tracks_balance and days > leave_services.remaining_days(employee, leave_type, start.year):
            raise serializers.ValidationError('Solde insuffisant.')
        attrs['days'] = days
        attrs['employee'] = employee
        return attrs


class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    worked_hours = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)

    class Meta:
        model = Attendance
        fields = ['id', 'employee', 'employee_name', 'date', 'check_in', 'check_out', 'status', 'source',
                  'note', 'worked_hours']
