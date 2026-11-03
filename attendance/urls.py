from django.urls import path

from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.MyAttendanceView.as_view(), name='mine'),
    path('pointer/', views.punch, name='punch'),
    path('registre/', views.RegisterView.as_view(), name='register'),
    path('rapport/', views.MonthlyReportView.as_view(), name='report'),
    path('saisir/', views.AttendanceCreateView.as_view(), name='create'),
    path('<int:pk>/modifier/', views.AttendanceUpdateView.as_view(), name='update'),
    path('<int:pk>/supprimer/', views.AttendanceDeleteView.as_view(), name='delete'),
    path('heures-sup/', views.OvertimeListView.as_view(), name='overtime_list'),
    path('heures-sup/saisir/', views.OvertimeCreateView.as_view(), name='overtime_create'),
    path('heures-sup/<int:pk>/modifier/', views.OvertimeUpdateView.as_view(), name='overtime_update'),
    path('heures-sup/<int:pk>/supprimer/', views.OvertimeDeleteView.as_view(), name='overtime_delete'),
    path('heures-sup/types/', views.OvertimeTypeListView.as_view(), name='overtime_type_list'),
    path('heures-sup/types/nouveau/', views.OvertimeTypeCreateView.as_view(), name='overtime_type_create'),
    path('heures-sup/types/<int:pk>/modifier/', views.OvertimeTypeUpdateView.as_view(),
         name='overtime_type_update'),
    path('heures-sup/types/<int:pk>/supprimer/', views.OvertimeTypeDeleteView.as_view(),
         name='overtime_type_delete'),
]
