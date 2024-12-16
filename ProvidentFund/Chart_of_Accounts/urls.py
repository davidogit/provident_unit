from django.urls import path
from Chart_of_Accounts import views

urlpatterns = [
    path('add-chart-of-accounts/',views.AddChartOfAccounts.as_view(), name="add_chart_of_account" ),
    path('delete-account/<int:pk>/', views.DeleteChartOfAccount.as_view(), name="delete_chart_of_account"),
    path('map-accounts/', views.AccountMappingView.as_view(), name='map_account'),
]