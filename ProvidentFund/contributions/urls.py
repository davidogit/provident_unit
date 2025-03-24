from django.urls import path
from . import views





urlpatterns =[
    path('<str:scheme_name>/staff/', views.StaffMemberListView.as_view(), name='staff_member_list'),
    path('<str:scheme_name>/staff/<int:pk>/', views.StaffMemberDetailView.as_view(), name='staff_member_detail'),
    path('<str:scheme_name>/staff/<int:pk>/opt-out/', views.OptOutMemberView.as_view(), name='opt_out_member'),
    path('<str:scheme_name>/member-contributions/<int:pk>/', views.Contributed.as_view(), name='contribution-history'),

    # Member Ajax search URL
    path('<str:scheme_name>/members/search/', views.AjaxStaffSearchView.as_view(), name='member_search'),
]
