from django.urls import path
from Member import views


urlpatterns=[
    # path('', views.LoginTemplateView.as_view(), name='loginView'),
    path('register/', views.registrationView, name='register'),
    path('login/', views.loginView, name='login'),
<<<<<<< HEAD
    # path('verify_otp/', views.verifyOtpView, name='verify_otp'),
    path('logout/',views.logoutView, name='logout')
=======
    path('verify_otp/', views.verifyOtpView, name='verify_otp'),
    path('logout/',views.logoutView, name='logout'),
    path('terms/', views.terms_and_conditions_view, name='terms_and_conditions'),
>>>>>>> a61d16d331a2003fdc43674ca74048345e57b54c
]