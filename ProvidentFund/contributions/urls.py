from django.urls import path
from . import views
from .views import ContributionsDetailView, StaffMemberListView, StaffMemberDetailView




urlpatterns =[
    path('', views.Invest.as_view(), name='finance_page'),
    path('ContributionsList/', views.ContributionsListView.as_view(), name='contributions_list'),
    path('ContributionsList2/', views.ContributionsListView2.as_view(), name='contributions_listpf2'),
    path('ContributionsDetailView/<int:pk>/', views.ContributionsDetailView.as_view(), name='contributions_details'),
    path('staff/', StaffMemberListView.as_view(), name='staff_member_list'),
    path('staff/<int:pk>/', StaffMemberDetailView.as_view(), name='staff_member_detail'),
]

