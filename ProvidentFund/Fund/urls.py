from django.urls import path
from . import views


urlpatterns =[
    path('', views.Invest.as_view(), name='finance_page'),
    path('addInvestment/', views.AddInvestment.as_view(), name='add_investment'),
    path('List/', views.InvestmentListView.as_view(), name='investment_list'),
    path('memberList/', views.MemberListView.as_view(), name='member_list'),
    path('<int:pk>/', views.MemberDetailView.as_view(), name='member_detail'),
    path('investmentDetail/<int:pk>/', views.InvestmentDetailView.as_view(), name='investment_detail'),
]