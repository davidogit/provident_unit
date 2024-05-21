from django.urls import path
from . import views


urlpatterns =[
    path('', views.Invest.as_view(), name='investment_form'),
    path('addInvestment/', views.AddInvestment.as_view(), name='addInvestment'),
    path('investmentList/', views.InvestMentList.as_view(), name='investment_list'),
    path('memberList/', views.MemberList.as_view(), name='member_list'),
]