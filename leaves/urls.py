from django.urls import path

from . import views

app_name = 'leaves'

urlpatterns = [
    path('', views.MyLeavesView.as_view(), name='my_leaves'),
    path('demander/', views.LeaveRequestCreateView.as_view(), name='create'),
    path('<int:pk>/', views.LeaveRequestDetailView.as_view(), name='detail'),
    path('<int:pk>/annuler/', views.leave_cancel, name='cancel'),
    path('<int:pk>/decision/', views.leave_decide, name='decide'),
    path('<int:pk>/justificatif/', views.leave_attachment, name='attachment'),
    path('calendrier/', views.LeaveCalendarView.as_view(), name='calendar'),
    path('toutes/', views.LeaveRequestListView.as_view(), name='list'),
    path('saisir/', views.HRLeaveCreateView.as_view(), name='hr_create'),
    path('soldes/', views.BalanceListView.as_view(), name='balances'),
    path('soldes/allouer/', views.balance_allocate, name='balance_allocate'),
    path('soldes/<int:pk>/modifier/', views.LeaveBalanceUpdateView.as_view(), name='balance_update'),
    path('types/', views.LeaveTypeListView.as_view(), name='type_list'),
    path('types/nouveau/', views.LeaveTypeCreateView.as_view(), name='type_create'),
    path('types/<int:pk>/modifier/', views.LeaveTypeUpdateView.as_view(), name='type_update'),
    path('types/<int:pk>/supprimer/', views.LeaveTypeDeleteView.as_view(), name='type_delete'),
    path('jours-feries/', views.HolidayListView.as_view(), name='holiday_list'),
    path('jours-feries/nouveau/', views.HolidayCreateView.as_view(), name='holiday_create'),
    path('jours-feries/<int:pk>/modifier/', views.HolidayUpdateView.as_view(), name='holiday_update'),
    path('jours-feries/<int:pk>/supprimer/', views.HolidayDeleteView.as_view(), name='holiday_delete'),
]
