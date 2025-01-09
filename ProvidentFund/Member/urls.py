from django.urls import path
from Member import views
from . import views
from .views import EditMemberProfileView,TransactionHistoryView, WithdrawalView, verify_transaction


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
    path('profile/<int:member_id>/', views.MemberPortal.as_view(), name='member_profile'),
    # path('member_dashboard/<int:member_id>/edit/', views.EditMemberProfileView.as_view(), name='edit_member_profile'),
    path('profile-edit/<int:member_id>/', views.EditMemberProfileView.as_view(), name='edit_member_profile'),

    # Scheme Application

    path('dashboard/<int:member_id>/', views.MemberDashboard.as_view(), name='member_dashboard'),
    path('application/<int:member_id>/', views.Application.as_view(), name='application_view'),

    path('active_schemes/<int:member_id>/', views.ActiveSchemes.as_view(), name='active_schemes'),
    path('pending_schemes/<int:member_id>/', views.PendingSchemes.as_view(), name='pending_schemes'),

    #Member Contributions
    path('<str:scheme_name>/member_contributions/<int:member_id>/', views.Contributed.as_view(), name='member_contribution'),
    path('create_transaction/<int:staff_id>/', views.CreateTransactionView.as_view(),name='create_transaction'),
    path('transaction_history/<int:staff_id>/', views.TransactionHistoryView.as_view(),  name='transaction_history'), 
    path('withdraw/<int:staff_id>/', WithdrawalView.as_view(), name='withdraw'),
    path('verify-transaction/<str:reference>/', verify_transaction, name='verify_transaction'),
    

]

