from django.urls import path
from Chart_of_Accounts import views

urlpatterns = [
    path('add-chart-of-accounts/',views.AddChartOfAccounts.as_view(), name="add_chart_of_account" ),
    path('delete-account/<int:pk>/', views.DeleteChartOfAccount.as_view(), name="delete_chart_of_account"),
    path('map-accounts/', views.AccountMappingView.as_view(), name='map_account'),
    path('delete-mapping/<int:pk>/', views.AccountMappingDeleteView.as_view(), name='delete_mapping'),
    path('fetch-account/<int:pk>/', views.FetchChartOfAccounts.as_view(), name='fetch_accounts'),
    path('update-account/<int:pk>/', views.UpdateChartOfAccounts.as_view(), name='update_accounts'),
    path('account-balances/', views.AccountBalanceQuery.as_view(), name='account_balances')
]