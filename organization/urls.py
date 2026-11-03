from django.urls import path

from . import views

app_name = 'organization'

urlpatterns = [
    path('departements/', views.DepartmentListView.as_view(), name='department_list'),
    path('departements/nouveau/', views.DepartmentCreateView.as_view(), name='department_create'),
    path('departements/<int:pk>/modifier/', views.DepartmentUpdateView.as_view(), name='department_update'),
    path('departements/<int:pk>/supprimer/', views.DepartmentDeleteView.as_view(), name='department_delete'),
    path('postes/', views.PositionListView.as_view(), name='position_list'),
    path('postes/nouveau/', views.PositionCreateView.as_view(), name='position_create'),
    path('postes/<int:pk>/modifier/', views.PositionUpdateView.as_view(), name='position_update'),
    path('postes/<int:pk>/supprimer/', views.PositionDeleteView.as_view(), name='position_delete'),
]
