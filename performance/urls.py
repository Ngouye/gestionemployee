from django.urls import path

from . import views

app_name = 'performance'

urlpatterns = [
    path('', views.my_reviews, name='mine'),
    path('campagnes/', views.CycleListView.as_view(), name='cycle_list'),
    path('campagnes/nouvelle/', views.CycleCreateView.as_view(), name='cycle_create'),
    path('campagnes/<int:pk>/', views.CycleDetailView.as_view(), name='cycle_detail'),
    path('campagnes/<int:pk>/modifier/', views.CycleUpdateView.as_view(), name='cycle_update'),
    path('campagnes/<int:pk>/supprimer/', views.CycleDeleteView.as_view(), name='cycle_delete'),
    path('campagnes/<int:pk>/generer/', views.cycle_generate, name='cycle_generate'),
    path('evaluation/<int:pk>/', views.ReviewDetailView.as_view(), name='review_detail'),
    path('evaluation/<int:pk>/enregistrer/', views.review_save, name='review_save'),
    path('objectifs/', views.ObjectiveListView.as_view(), name='objective_list'),
    path('objectifs/nouveau/', views.ObjectiveCreateView.as_view(), name='objective_create'),
    path('objectifs/<int:pk>/modifier/', views.ObjectiveUpdateView.as_view(), name='objective_update'),
    path('objectifs/<int:pk>/supprimer/', views.ObjectiveDeleteView.as_view(), name='objective_delete'),
]
