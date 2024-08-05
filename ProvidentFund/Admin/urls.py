

from django.urls import path
from . import views

urlpatterns = [
    path('admin_panel/', views.admin_panel, name='admin_panel'),
    path('admin_login/', views.custom_login, name='admin_login'),
    path('assign_roles/', views.assign_roles, name='assign_roles'),
    path('add_user/', views.add_user, name='add_user'),
    path('manage_users/', views.manage_users, name='manage_users'),
    path('delete_group/<int:group_id>/', views.delete_group, name='delete_group'),
    # path('profile/', views.profile_view, name='profile'),
    path('edit_user/<int:id>/', views.edit_user_view, name='edit_user'),  
    path('delete_user/<int:id>/', views.delete_user_view, name='delete_user'),
    # path('admin_page/', views.admin_page, name='admin_page'),
    # path('hr_page/', views.hr_page, name='hr_page'),
    # path('finance_page/', views.finance_page, name='finance_page'),
]
