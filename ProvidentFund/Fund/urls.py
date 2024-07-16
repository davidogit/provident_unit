from django.contrib import admin
from django.urls import path, include
from . import views
from django.contrib.auth.decorators import login_required

urlpatterns =[
    path('', views.Invest.as_view(), name='finance_page'),
    path('addInvestment/', views.AddInvestment.as_view(), name='add_investment'),
    path('investmentList/', views.InvestmentListView.as_view(), name='investment_list'),
    path('memberList/', views.MemberListView.as_view(), name='member_list'),
    path('<int:pk>/', views.MemberDetailView.as_view(), name='member_detail'),
    path('investmentDetail/<int:pk>/', views.InvestmentDetailView.as_view(), name='investment_detail'),
    # path('addMember/', views.AddMemberView.as_view(), name='add_member'),
    path('update/<int:pk>', views.InvestmentUpdateView.as_view(), name='investment_update'),
    path('memberUpdate/<int:pk>/', views.MemberUpdateView.as_view(), name='member_update'),
    path('deleteMember/<int:pk>/', views.MemberDeleteView.as_view(), name='delete_member'),
    path('deleteInvestment/<int:pk>/', views.InvestmentDeleteView.as_view(), name='delete_investment'),
    path('investmentRollover/<int:pk>/', views.RolloverPercentage.as_view(), name='rollover_percentage'),
    path('investment_query/', views.InvestmentQuery.as_view(), name='query'),

    # Bank Interest Related URLS
    path('add_bank_interest/', views.BankInterestCreateView.as_view(), name='add_bank_interest'),
    path('bank_interest_list/', views.BankInterestListView.as_view(), name='bank_interest_list'),
    path('bank-interest-query/', views.BankInterestQuery.as_view(), name='bank_interest_query'),

    #Delayed Interest Related URLS 
    path('add_delayed_interest/', views.DelayedInterestCreateView.as_view(), name='add_delayed_interest'),
    path('delayed_interst_list/', views.DelayedInterestListView.as_view(), name='delayed_interest_list'),

    
]