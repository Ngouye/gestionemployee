from django.urls import path

from . import views

app_name = 'employees'

urlpatterns = [
    path('', views.EmployeeListView.as_view(), name='list'),
    path('nouveau/', views.EmployeeCreateView.as_view(), name='create'),
    path('importer/', views.employee_import, name='import'),
    path('annuaire/', views.DirectoryView.as_view(), name='directory'),
    path('organigramme/', views.org_chart, name='org_chart'),
    path('mon-profil/', views.my_profile, name='my_profile'),
    path('mon-profil/modifier/', views.MyProfileUpdateView.as_view(), name='my_profile_update'),
    path('<int:pk>/', views.EmployeeDetailView.as_view(), name='detail'),
    path('<int:pk>/modifier/', views.EmployeeUpdateView.as_view(), name='update'),
    path('<int:pk>/supprimer/', views.EmployeeDeleteView.as_view(), name='delete'),
    path('<int:pk>/photo/', views.employee_photo, name='photo'),
    path('<int:pk>/acces/', views.employee_account, name='account'),
    path('<int:pk>/attestation-de-travail/', views.employment_letter, {'kind': 'attestation'},
         name='work_attestation'),
    path('<int:pk>/certificat-de-travail/', views.employment_letter, {'kind': 'certificat'},
         name='work_certificate'),
    path('mon-profil/demander-attestation/', views.request_attestation, name='request_attestation'),
    path('<int:pk>/documents/ajouter/', views.document_upload, name='document_upload'),
    path('<int:employee_pk>/contrats/nouveau/', views.ContractCreateView.as_view(), name='contract_create'),
    path('contrats/', views.ContractListView.as_view(), name='contract_list'),
    path('contrats/<int:pk>/modifier/', views.ContractUpdateView.as_view(), name='contract_update'),
    path('contrats/<int:pk>/supprimer/', views.ContractDeleteView.as_view(), name='contract_delete'),
    path('contrats/<int:pk>/telecharger/', views.contract_download, name='contract_download'),
    path('documents/<int:pk>/telecharger/', views.document_download, name='document_download'),
    path('documents/<int:pk>/supprimer/', views.document_delete, name='document_delete'),
]
