from django.urls import path

from . import views

app_name = 'expenses'

urlpatterns = [
    path('', views.MyExpensesView.as_view(), name='mine'),
    path('nouvelle/', views.ExpenseCreateView.as_view(), name='create'),
    path('toutes/', views.ExpenseListView.as_view(), name='list'),
    path('<int:pk>/', views.ExpenseDetailView.as_view(), name='detail'),
    path('<int:pk>/decision/', views.expense_decide, name='decide'),
    path('<int:pk>/rembourser/', views.expense_mark_paid, name='pay'),
    path('<int:pk>/supprimer/', views.expense_delete, name='delete'),
    path('<int:pk>/justificatif/', views.expense_receipt, name='receipt'),
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/nouvelle/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/modifier/', views.CategoryUpdateView.as_view(), name='category_update'),
    path('categories/<int:pk>/supprimer/', views.CategoryDeleteView.as_view(), name='category_delete'),
]
