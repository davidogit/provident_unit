from django.urls import path
from . import views
from . import views




urlpatterns =[
    path('', views.Invest.as_view(), name='finance_page'),
    path('staff/', views.StaffMemberListView.as_view(), name='staff_member_list'),
    path('staff/<int:pk>/', views.StaffMemberDetailView.as_view(), name='staff_member_detail'),
    path('staff/<int:pk>/opt-out/', views.OptOutMemberView.as_view(), name='opt_out_member'),
    path('member-contributions/<int:membership_id>/', views.Contributed.as_view(), name='contribution-history'),
]


