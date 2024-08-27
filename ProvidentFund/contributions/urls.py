from django.urls import path
from . import views





urlpatterns =[
    path('<str:scheme_name>/staff/', views.StaffMemberListView.as_view(), name='staff_member_list'),
    path('<str:scheme_name>/staff/<int:pk>/', views.StaffMemberDetailView.as_view(), name='staff_member_detail'),
    path('<str:scheme_name>/staff/<int:pk>/opt-out/', views.OptOutMemberView.as_view(), name='opt_out_member'),
    path('<str:scheme_name>/member-contributions/<int:pk>/', views.Contributed.as_view(), name='contribution-history'),
    path('member_dashboard/<int:member_id>/', views.MemberPortal.as_view(), name='member_profile'),
    path('member_dashboard/<int:member_id>/edit/', views.EditMemberProfileView.as_view(), name='edit_member_profile'),
]
