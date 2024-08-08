from django.urls import path
from Member import views


urlpatterns=[
    # path('', views.LoginTemplateView.as_view(), name='loginView'),
    path('register/', views.registrationView, name='register'),
    path('member_login/', views.loginView, name='member_login'),
    # path('verify_otp/', views.verifyOtpView, name='verify_otp'),
    # path('logout/',views.logoutView, name='logout'),
    path('verify_otp/<int:user_id>', views.verifyOtpView, name='verify_otp'),
    path('logout/',views.logoutView, name='logout'),
    path('terms/', views.terms_and_conditions_view, name='terms_and_conditions'),

    path('invalid-login-details/', views.InvalidLoginDetails.as_view(), name='invalid_login_details'),

]