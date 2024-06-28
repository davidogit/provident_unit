from django.urls import path
from . import views
from django.contrib.auth.decorators import login_required

urlpatterns =[
    path('', views.Invest.as_view(), name='finance_page'),
    path('addInvestment/', views.AddInvestment.as_view(), name='add_investment'),
    path('investmentList/', views.InvestmentListView.as_view(), name='investment_list'),
    path('memberList/', views.MemberListView.as_view(), name='member_list'),
    path('<int:pk>/', views.MemberDetailView.as_view(), name='member_detail'),
    path('investmentDetail/<int:pk>/', views.InvestmentDetailView.as_view(), name='investment_detail'),
    path('addMember/', views.AddMemberView.as_view(), name='add_member'),
    path('update/<int:pk>', views.InvestmentUpdateView.as_view(), name='investment_update'),
    path('memberUpdate/<int:pk>/', views.MemberUpdateView.as_view(), name='member_update'),
    path('deleteMember/<int:pk>/', views.MemberDeleteView.as_view(), name='delete_member'),
    path('deleteInvestment/<int:pk>/', views.InvestmentDeleteView.as_view(), name='delete_investment'),
    path('investmentRollover/<int:pk>/', views.RolloverPercentage.as_view(), name='rollover_percentage'),
    path('investment_query/', views.InvestmentQuery.as_view(), name='query'),

]