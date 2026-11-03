from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from attendance.models import Attendance
from employees.models import Employee
from leaves.models import LeaveRequest, LeaveType
from leaves.services import balances_for, notify_new_request
from organization.models import Department, Position

from .serializers import (AttendanceSerializer, DepartmentSerializer, EmployeePublicSerializer, EmployeeSerializer,
                          LeaveRequestSerializer, LeaveTypeSerializer, PositionSerializer)


class IsHROrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_authenticated and request.user.is_hr


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsHROrReadOnly]


class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.select_related('department')
    serializer_class = PositionSerializer
    permission_classes = [IsHROrReadOnly]


class EmployeeViewSet(viewsets.ModelViewSet):
    """Employés : fiche complète pour les RH, annuaire pour les autres."""

    permission_classes = [IsHROrReadOnly]

    def get_queryset(self):
        queryset = Employee.objects.select_related('department', 'position').prefetch_related('contracts')
        if not self.request.user.is_hr:
            queryset = queryset.filter(status=Employee.Status.ACTIVE)
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(Q(first_name__icontains=search) | Q(last_name__icontains=search)
                                       | Q(email__icontains=search) | Q(employee_id__icontains=search))
        department = self.request.query_params.get('department')
        if department:
            queryset = queryset.filter(department_id=department)
        return queryset

    def get_serializer_class(self):
        return EmployeeSerializer if self.request.user.is_hr else EmployeePublicSerializer


class LeaveTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LeaveType.objects.filter(is_active=True)
    serializer_class = LeaveTypeSerializer


class LeaveRequestViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    """Demandes de congé : les siennes (ou toutes pour les RH) ; création pour soi-même."""

    serializer_class = LeaveRequestSerializer

    def get_queryset(self):
        queryset = LeaveRequest.objects.select_related('employee', 'leave_type')
        user = self.request.user
        if user.is_hr:
            status = self.request.query_params.get('status')
            return queryset.filter(status=status) if status else queryset
        employee = user.employee_profile
        if employee is None:
            return queryset.none()
        return queryset.filter(Q(employee=employee) | Q(employee__manager=employee))

    def perform_create(self, serializer):
        leave = serializer.save()
        notify_new_request(leave, actor=self.request.user)


class AttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AttendanceSerializer

    def get_queryset(self):
        queryset = Attendance.objects.select_related('employee')
        user = self.request.user
        if not user.is_hr:
            employee = user.employee_profile
            queryset = queryset.filter(employee=employee) if employee else queryset.none()
        date = self.request.query_params.get('date')
        if date:
            queryset = queryset.filter(date=date)
        return queryset


@api_view(['GET'])
def me(request):
    user = request.user
    employee = user.employee_profile
    data = {
        'id': user.pk, 'email': user.email, 'first_name': user.first_name, 'last_name': user.last_name,
        'role': user.role, 'role_label': user.get_role_display(), 'employee': None,
    }
    if employee:
        data['employee'] = EmployeePublicSerializer(employee).data
        data['leave_balances'] = [
            {'leave_type': b['leave_type'].name, 'total': b['total'], 'used': b['used'],
             'pending': b['pending'], 'remaining': b['remaining']}
            for b in balances_for(employee, timezone.localdate().year)
        ]
    return Response(data)
