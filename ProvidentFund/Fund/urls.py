from django.urls import path
from . import views


urlpatterns =[
    path('', views.Invest.as_view(), name='investment_form'),
    path('addInvestment/', views.AddInvestment.as_view(), name='add_investment'),
    path('List/', views.InvestmentListView.as_view(), name='investment_list'),
    path('memberList/', views.MemberList.as_view(), name='member_list'),
    
]