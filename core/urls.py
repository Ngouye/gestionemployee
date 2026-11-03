from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('validations/', views.approvals, name='approvals'),
    path('notifications/', views.NotificationListView.as_view(), name='notifications'),
    path('notifications/<int:pk>/', views.notification_open, name='notification_open'),
    path('notifications/tout-lire/', views.notifications_mark_all, name='notifications_mark_all'),
    path('annonces/', views.AnnouncementFeedView.as_view(), name='announcements'),
    path('annonces/gestion/', views.AnnouncementAdminListView.as_view(), name='announcement_admin'),
    path('annonces/nouvelle/', views.AnnouncementCreateView.as_view(), name='announcement_create'),
    path('annonces/<int:pk>/modifier/', views.AnnouncementUpdateView.as_view(), name='announcement_update'),
    path('annonces/<int:pk>/supprimer/', views.AnnouncementDeleteView.as_view(), name='announcement_delete'),
    path('administration/parametres/', views.CompanySettingsView.as_view(), name='settings'),
    path('administration/journal/', views.AuditLogView.as_view(), name='audit_log'),
    path('logo/', views.company_logo, name='company_logo'),
    path('sante/', views.health, name='health'),
]
