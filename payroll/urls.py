from django.urls import path

from . import views

app_name = 'payroll'

urlpatterns = [
    path('periodes/', views.PeriodListView.as_view(), name='period_list'),
    path('periodes/nouvelle/', views.PeriodCreateView.as_view(), name='period_create'),
    path('periodes/<int:pk>/', views.PeriodDetailView.as_view(), name='period_detail'),
    path('periodes/<int:pk>/calculer/', views.period_generate, name='period_generate'),
    path('periodes/<int:pk>/valider/', views.period_validate, name='period_validate'),
    path('periodes/<int:pk>/payer/', views.period_mark_paid, name='period_pay'),
    path('periodes/<int:pk>/rouvrir/', views.period_reopen, name='period_reopen'),
    path('periodes/<int:pk>/supprimer/', views.PeriodDeleteView.as_view(), name='period_delete'),
    path('bulletins/<int:pk>/', views.PayslipDetailView.as_view(), name='payslip_detail'),
    path('bulletins/<int:pk>/pdf/', views.payslip_pdf, name='payslip_pdf'),
    path('mes-bulletins/', views.MyPayslipsView.as_view(), name='my_payslips'),
    path('cotisations/', views.RuleListView.as_view(), name='rule_list'),
    path('cotisations/nouvelle/', views.RuleCreateView.as_view(), name='rule_create'),
    path('cotisations/<int:pk>/modifier/', views.RuleUpdateView.as_view(), name='rule_update'),
    path('cotisations/<int:pk>/supprimer/', views.RuleDeleteView.as_view(), name='rule_delete'),
    path('bareme-impot/', views.BracketListView.as_view(), name='bracket_list'),
    path('bareme-impot/nouvelle/', views.BracketCreateView.as_view(), name='bracket_create'),
    path('bareme-impot/<int:pk>/modifier/', views.BracketUpdateView.as_view(), name='bracket_update'),
    path('bareme-impot/<int:pk>/supprimer/', views.BracketDeleteView.as_view(), name='bracket_delete'),
    path('elements/', views.SalaryItemListView.as_view(), name='item_list'),
    path('elements/nouveau/', views.SalaryItemCreateView.as_view(), name='item_create'),
    path('elements/<int:pk>/modifier/', views.SalaryItemUpdateView.as_view(), name='item_update'),
    path('elements/<int:pk>/supprimer/', views.SalaryItemDeleteView.as_view(), name='item_delete'),
]
