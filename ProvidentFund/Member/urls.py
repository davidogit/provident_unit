from django.urls import path
from Member import views
from . import views
from .views import EditMemberProfileView


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
    path('member_dashboard/<int:member_id>/', views.MemberPortal.as_view(), name='member_profile'),
    # path('member_dashboard/<int:member_id>/edit/', views.EditMemberProfileView.as_view(), name='edit_member_profile'),
    path('member_dashboard/<int:member_id>/edit/', views.EditMemberProfileView.as_view(), name='edit_member_profile'),

]

