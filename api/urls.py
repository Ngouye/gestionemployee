from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'api'

router = DefaultRouter()
router.register('departements', views.DepartmentViewSet, basename='department')
router.register('postes', views.PositionViewSet, basename='position')
router.register('employes', views.EmployeeViewSet, basename='employee')
router.register('types-conges', views.LeaveTypeViewSet, basename='leavetype')
router.register('conges', views.LeaveRequestViewSet, basename='leaverequest')
router.register('presences', views.AttendanceViewSet, basename='attendance')

urlpatterns = [
    path('', include(router.urls)),
    path('moi/', views.me, name='me'),
    path('jeton/', obtain_auth_token, name='token'),
]
