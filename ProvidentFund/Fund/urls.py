from django.contrib import admin
from django.urls import path, include
from . import views
from django.contrib.auth.decorators import login_required

urlpatterns =[
    path('', views.LandingPage.as_view(), name='landing_page'),
    path('dashboard', views.Invest.as_view(), name='finance_page'),
    path('<int:scheme_name>/addInvestment/', views.AddInvestment.as_view(), name='add_investment'),
    path('<int:scheme_name>/investmentList/', views.InvestmentListView.as_view(), name='investment_list'),
    path('<int:scheme_name>/memberList/', views.MemberListView.as_view(), name='member_list'),
    path('<int:scheme_name>/<int:pk>/', views.MemberDetailView.as_view(), name='member_detail'),
    path('<int:scheme_name>/investmentDetail/<int:pk>/', views.InvestmentDetailView.as_view(), name='investment_detail'),
    
    path('<int:scheme_name>/update/<int:pk>', views.InvestmentUpdateView.as_view(), name='investment_update'),
    path('<int:scheme_name>/deleteInvestment/<int:pk>/', views.InvestmentDeleteView.as_view(), name='delete_investment'),
    path('<int:scheme_name>/investmentRollover/<int:pk>/', views.RolloverPercentage.as_view(), name='rollover_percentage'),
    path('<int:scheme_name>/investment_query/', views.InvestmentQuery.as_view(), name='query'),

    # Member URLS
    path('<int:scheme_name>/memberUpdate/<int:pk>/', views.MemberUpdateView.as_view(), name='member_update'),
    path('<int:scheme_name>/deleteMember/<int:pk>/', views.MemberDeleteView.as_view(), name='delete_member'),
    path('<int:scheme_name>/exited-members/', views.ExitedMembers.as_view(), name='exited_members'),

    # Bank Interest Related URLS
    path('<int:scheme_name>/add_bank_interest/', views.BankInterestCreateView.as_view(), name='add_bank_interest'),
    path('<int:scheme_name>/bank_interest_list/', views.BankInterestListView.as_view(), name='bank_interest_list'),
    path('<int:scheme_name>/bank-interest-query/', views.BankInterestQuery.as_view(), name='bank_interest_query'),

    #Delayed Interest Related URLS 
    path('<int:scheme_name>/add_delayed_interest/', views.DelayedInterestCreateView.as_view(), name='add_delayed_interest'),
    path('<int:scheme_name>/delayed_interest_list/', views.DelayedInterestListView.as_view(), name='delayed_interest_list'),
    path('<int:scheme_name>/delayed-interest-query/', views.DelayedInterestQuery.as_view(), name='delayed_interest_query'),

    # OTHERS
    path('access_denied/', views.AccessDenied.as_view(), name='access_denied'),
    
]