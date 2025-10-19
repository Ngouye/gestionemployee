from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
#from .views import custom_logout_view # Importez votre fonction


from django.shortcuts import redirect

def redirect_to_employee_list(request):
    return redirect('employee_list')

urlpatterns = [
path('', views.employee_list, name='employee_list'),
path('add/', views.employee_create, name='employee_create'),
path('edit/<int:pk>/', views.employee_update, name='employee_update'),
path('delete/<int:pk>/', views.employee_delete, name='employee_delete'),
path('accounts/profile/', redirect_to_employee_list, name='user_profile_redirect'),
]