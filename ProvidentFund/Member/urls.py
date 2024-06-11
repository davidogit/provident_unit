from django.urls import path
from Member import views


urlpatterns=[
    # path('', views.LoginTemplateView.as_view(), name='loginView'),
    path('register/', views.registrationView, name='register'),
    path('login/', views.loginView, name='login'),
    path('logout/',views.logoutView, name='logout')
]