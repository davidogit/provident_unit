from django.urls import path
from . import views

urlpatterns = [
    path('<int:staff_id>/', views.LoanApplicationView.as_view(), name="loan_application"),
    path('my-loans/<int:staff_id>/', views.MemberLoanPage.as_view(), name="my_loans"),
    path('calculate-details/',views.CalculatePotentialLoan.as_view()),
    path('apply/<int:staff_id>/', views.HandleLoanSubmission.as_view()),
    path('approve-loans/',views.LoanApprovalView.as_view(), name='approve_loans'),
    path('disburse_approved_loans/', views.DisburseApprovedLoans.as_view(), name='disburse_approved_loans'),
    path('approved-loan-details/<int:approved_loan_id>/',views.FetchLoanDetails.as_view()),
    path('rejected-applications/', views.RejectedLoanApplications.as_view(), name='rejected_loans')
]