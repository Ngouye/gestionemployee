from django.urls import path

from . import views

app_name = 'recruitment'

urlpatterns = [
    path('offres/', views.JobListView.as_view(), name='job_list'),
    path('offres/nouvelle/', views.JobCreateView.as_view(), name='job_create'),
    path('offres/<int:pk>/', views.JobDetailView.as_view(), name='job_detail'),
    path('offres/<int:pk>/modifier/', views.JobUpdateView.as_view(), name='job_update'),
    path('offres/<int:pk>/supprimer/', views.JobDeleteView.as_view(), name='job_delete'),
    path('candidatures/', views.ApplicationListView.as_view(), name='application_list'),
    path('candidatures/nouvelle/', views.ApplicationCreateView.as_view(), name='application_create'),
    path('candidatures/<int:pk>/', views.ApplicationDetailView.as_view(), name='application_detail'),
    path('candidatures/<int:pk>/modifier/', views.ApplicationUpdateView.as_view(), name='application_update'),
    path('candidatures/<int:pk>/supprimer/', views.ApplicationDeleteView.as_view(), name='application_delete'),
    path('candidatures/<int:pk>/etape/', views.application_move, name='application_move'),
    path('candidatures/<int:pk>/cv/', views.application_resume, name='application_resume'),
    path('candidatures/<int:application_pk>/entretiens/nouveau/', views.interview_create, name='interview_create'),
    path('entretiens/', views.InterviewListView.as_view(), name='interview_list'),
    path('entretiens/<int:pk>/', views.InterviewFeedbackView.as_view(), name='interview_feedback'),
    path('entretiens/<int:pk>/supprimer/', views.interview_delete, name='interview_delete'),
    # Page carrières publique
    path('carrieres/', views.careers_list, name='careers_list'),
    path('carrieres/<int:pk>/', views.careers_detail, name='careers_detail'),
    path('carrieres/merci/', views.careers_thanks, name='careers_thanks'),
]
