from django.contrib import admin
from django.urls import include, path

admin.site.site_header = 'EmployeeManager — Administration technique'
admin.site.site_title = 'EmployeeManager'
admin.site.index_title = 'Administration'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('compte/', include('accounts.urls')),
    path('', include('core.urls')),
    path('organisation/', include('organization.urls')),
    path('employes/', include('employees.urls')),
    path('conges/', include('leaves.urls')),
    path('presences/', include('attendance.urls')),
    path('paie/', include('payroll.urls')),
    path('notes-de-frais/', include('expenses.urls')),
    path('recrutement/', include('recruitment.urls')),
    path('evaluations/', include('performance.urls')),
    path('formations/', include('training.urls')),
    path('api/v1/', include('api.urls')),
]

handler403 = 'core.views.error_403'
handler404 = 'core.views.error_404'
handler500 = 'core.views.error_500'
