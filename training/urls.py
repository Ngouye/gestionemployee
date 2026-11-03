from django.urls import path

from . import views

app_name = 'training'

urlpatterns = [
    path('', views.TrainingListView.as_view(), name='list'),
    path('nouvelle/', views.TrainingCreateView.as_view(), name='create'),
    path('mes-formations/', views.my_trainings, name='mine'),
    path('<int:pk>/', views.TrainingDetailView.as_view(), name='detail'),
    path('<int:pk>/modifier/', views.TrainingUpdateView.as_view(), name='update'),
    path('<int:pk>/supprimer/', views.TrainingDeleteView.as_view(), name='delete'),
    path('<int:pk>/inscrire/', views.enroll, name='enroll'),
    path('<int:pk>/demander/', views.request_training, name='request'),
    path('participants/<int:pk>/modifier/', views.participant_update, name='participant_update'),
    path('participants/<int:pk>/retirer/', views.participant_remove, name='participant_remove'),
    path('participants/<int:pk>/avis/', views.submit_feedback, name='feedback'),
    path('participants/<int:pk>/attestation/', views.certificate_download, name='certificate'),
]
