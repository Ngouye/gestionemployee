from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('connexion/', views.LoginView.as_view(), name='login'),
    path('deconnexion/', views.LogoutView.as_view(), name='logout'),
    path('profil/', views.profile, name='profile'),
    path('profil/jeton-api/', views.api_token, name='api_token'),
    path('mot-de-passe/', views.PasswordChangeView.as_view(), name='password_change'),
    path('mot-de-passe-oublie/', views.PasswordResetView.as_view(), name='password_reset'),
    path('mot-de-passe-oublie/envoye/', views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reinitialiser/<uidb64>/<token>/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reinitialiser/termine/', views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('utilisateurs/', views.UserListView.as_view(), name='user_list'),
    path('utilisateurs/nouveau/', views.UserCreateView.as_view(), name='user_create'),
    path('utilisateurs/<int:pk>/modifier/', views.UserUpdateView.as_view(), name='user_update'),
    path('utilisateurs/<int:pk>/mot-de-passe/', views.user_reset_password, name='user_reset_password'),
]
