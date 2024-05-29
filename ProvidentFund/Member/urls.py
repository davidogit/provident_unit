from django.urls import path
from Member import views


urlpatterns=[
    path('', views.LoginView.as_view(), name='loginView')

]