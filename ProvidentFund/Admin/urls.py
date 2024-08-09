from django.urls import path
from . import views


urlpatterns = [
    path('admin_panel/', views.admin_panel, name='admin_panel'),

    path('admin_login/', views.custom_login, name='admin_login'),
    path('logout/',views.logoutView, name='logout'),

    path('assign_roles/', views.assign_roles, name='assign_roles'),
    path('add_user/', views.add_user, name='add_user'),
    path('manage_users/', views.manage_users, name='manage_users'),

    path('delete_group/<int:group_id>/', views.delete_group, name='delete_group'),
    path('delete_user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('edit_user/<int:id>/', views.edit_user_view, name='edit_user'),
    
    # path('profile/', views.profile_view, name='profile'),
    
   
]
