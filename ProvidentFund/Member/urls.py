from django.urls import path
from Member import views


urlpatterns=[
    path('', views.LoginTemplateView.as_view(), name='loginView')

]