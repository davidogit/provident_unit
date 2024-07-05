# Admin/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('admin_panel/', views.admin_panel, name='admin_panel'),
    path('assign_roles/', views.assign_roles, name='assign_roles'),
    path('add_user/', views.add_user, name='add_user'),
    path('manage_users/', views.manage_users, name='manage_users'),
]
