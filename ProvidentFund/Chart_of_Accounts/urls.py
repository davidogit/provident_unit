from django.urls import path
from Chart_of_Accounts import views

urlpatterns = [
    path('add-chart-of-accounts/',views.AddChartOfAccounts.as_view(), name="add_chart_of_account" ),
    path('delete-account/<int:pk>/', views.DeleteChartOfAccount.as_view(), name="delete_chart_of_account"),
    path('map-accounts/', views.AccountMappingView.as_view(), name='map_account'),
    path('delete-mapping/<int:pk>/', views.AccountMappingDeleteView.as_view(), name='delete_mapping'),
    path('fetch-account/<int:pk>/', views.FetchChartOfAccounts.as_view(), name='fetch_accounts'),
    path('update-account/<int:pk>/', views.UpdateChartOfAccounts.as_view(), name='update_accounts'),
    path('account-balances/', views.AccountBalanceQuery.as_view(), name='account_balances'),
    path('bank-accounts/', views.BankAccountsView.as_view(), name='bank_accounts'),
    path('delete-bank-account/<int:pk>/', views.DeleteBankView.as_view(), name='delete_bank'),
    path('update-bank-account/<int:pk>/', views.BankUpdateView.as_view(), name='update_bank'),
    path('fetch-bank-account/<int:pk>/', views.FetchBankDetail.as_view(), name='fetch_bank_details'),
    # Search bank accounts
    path('search-bank/', views.BankAccountSearchView.as_view(), name='search-bank'),
    path('update-mapping/<int:pk>/', views.AccountMappingUpdateView.as_view(), name='update_mapping'),
    path('account-parameters/', views.SetAccountParameters.as_view(), name='account_parameters'),
    path('get-child-accounts/', views.FetchChildrenAccounts.as_view(),name='get_child_accounts'),
    path('get-account-transactions/<int:account_id>/', views.FetchAccountTransactions.as_view(),name='fetch_account_transactions'),
]