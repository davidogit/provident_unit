# Admin/urls.py

from django.urls import path
from . import views
from .views import edit_user_view
from .views import delete_user_view



urlpatterns = [
    path('admin_panel/', views.admin_panel, name='admin_panel'),
    path('assign_roles/', views.assign_roles, name='assign_roles'),
    path('add_user/', views.add_user, name='add_user'),
    path('manage_users/', views.manage_users, name='manage_users'),
    path('delete_group/<int:group_id>/', views.delete_group, name='delete_group'),
    path('profile/', views.profile_view, name='profile'),
    path('edit_user/<int:id>/', edit_user_view, name='edit_user'),  
    path('delete_user/<int:id>/', delete_user_view, name='delete_user'),
]
