from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns =[
    path('', views.LandingPage.as_view(), name='landing_page'),
    path('dashboard', views.Invest.as_view(), name='finance_page'),
    path('<int:scheme_name>/addInvestment/', views.AddInvestment.as_view(), name='add_investment'),
    path('<int:scheme_name>/investmentList/', views.InvestmentListView.as_view(), name='investment_list'),
    path('<int:scheme_name>/memberList/', views.MemberListView.as_view(), name='member_list'),
    path('<int:scheme_name>/<int:pk>/', views.MemberDetailView.as_view(), name='member_detail'),
    path('<int:scheme_name>/investmentDetail/<int:pk>/', views.InvestmentDetailView.as_view(), name='investment_detail'),
    path('<int:scheme_name>/ivestment_approval/', views.InvestmentApproval.as_view(), name='investment_approval'),
    path('<int:scheme_name>/approved_investments/', views.ApprovedInvestments.as_view(), name='approved_investments'),
    
    path('<int:scheme_name>/update/<int:pk>', views.InvestmentUpdateView.as_view(), name='investment_update'),
    path('<int:scheme_name>/deleteInvestment/<int:pk>/', views.InvestmentDeleteView.as_view(), name='delete_investment'),
    path('<int:scheme_name>/investmentRollover/<int:pk>/', views.RolloverPercentage.as_view(), name='rollover_percentage'),
    path('<int:scheme_name>/investment_query/', views.InvestmentQuery.as_view(), name='query'),

    # Member URLS
    # path('<int:scheme_name>/memberUpdate/<int:pk>/', views.MemberUpdateView.as_view(), name='member_update'),
    # path('<int:scheme_name>/deleteMember/<int:pk>/', views.MemberDeleteView.as_view(), name='delete_member'),
    path('<int:scheme_name>/exited-members/', views.ExitedMembers.as_view(), name='exited_members'),

    # Bank Interest Related URLS
    # path('<int:scheme_name>/add_bank_interest/', views.BankInterestCreateView.as_view(), name='add_bank_interest'),
    # path('<int:scheme_name>/bank_interest_list/', views.BankInterestListView.as_view(), name='bank_interest_list'),
    # path('<int:scheme_name>/bank-interest-query/', views.BankInterestQuery.as_view(), name='bank_interest_query'),

    #Delayed Interest Related URLS 
    # path('<int:scheme_name>/add_delayed_interest/', views.DelayedInterestCreateView.as_view(), name='add_delayed_interest'),
    path('<int:scheme_name>/delayed_interest_list/', views.DelayedInterestListView.as_view(), name='delayed_interest_list'),
    path('<int:scheme_name>/delayed-interest-query/', views.DelayedInterestQuery.as_view(), name='delayed_interest_query'),

    # OTHERS
    path('access_denied/', views.AccessDenied.as_view(), name='access_denied'),

    # Scheme Approval
    path('approvals/', views.ToBeApproved.as_view(), name='scheme_approval'),

    # History of investments
    path('recent_activities/', views.RecentActivities.as_view(), name='recent_activities'),

    # contribution approval
    path('<int:scheme_name>/approve-contributions/', views.ApproveContributions.as_view(), name='approve_contributions'),

    # Endpoint for contribution data fetch
    path('<int:scheme_name>/fetch_contributions/', views.FetchContributions.as_view(), name='fetch-contributions'),

    # Exit Meber approval url
    path('exiting_members/', views.ApproveExitedMembers.as_view(), name='approve_exit_members'),


    # Mass Member Upload
    path('mass_upload/', views.MassMemberUpload.as_view(), name='mass_enroll'),


    # Payout URLs
    path('general-payout/', views.GeneralPayoutView.as_view(), name='general_payout'),
    
]