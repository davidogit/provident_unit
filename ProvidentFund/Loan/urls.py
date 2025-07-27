from django.urls import path
from . import views

urlpatterns = [
    path('<int:staff_id>/', views.LoanApplicationView.as_view(), name="loan_application"),
    path('my-loans/<int:staff_id>/', views.MemberLoanPage.as_view(), name="my_loans"),
    path('calculate-details/',views.CalculatePotentialLoan.as_view()),
    path('apply/<int:staff_id>/', views.HandleLoanSubmission.as_view()),
    path('approve-loans/',views.LoanApprovalView.as_view(), name='approve_loans'),
    path('disburse_approved_loans/', views.DisburseApprovedLoans.as_view(), name='disburse_approved_loans'),
    path('loan-details/<int:loan_id>/',views.FetchLoanDetails.as_view()),
    path('rejected-applications/', views.RejectedLoanApplications.as_view(), name='rejected_loans'),
    path('loan-types/', views.LoanTypeView.as_view(), name='loan_types'),
    path('add-loan-type/', views.CreateLoanType.as_view(),name='add_loan_type'),
    path('loan-type-details/<int:pk>/', views.LoanTypeDetail.as_view()),
    path('update-loan-type/<int:pk>/', views.LoanTypeUpdate.as_view()),
    path('delete-loan-type/<int:pk>/', views.LoanTypeDelete.as_view()),
    path('<int:staff_id>/loan_types/', views.MemberLoanTypeView.as_view(), name='member_loan_type'),
    path('fetch_loan_type_details/', views.FetchLoanTypeDetails.as_view(), name='fetch_loan_types'),
    path('<int:staff_id>/member-loan-details/<int:pk>/', views.MemberLoanDetailView.as_view(), name='member_loan_details'),
    path('disbursed-loans/', views.DisbursedLoans.as_view(), name='disbursed_loans'),
    path('disbursed-loan-details/<int:pk>/', views.DisbursedLoanDetailView.as_view(), name='disbursed_loan_details'),
    path('admin-loan-repayment/', views.LoanPaymentHandler.as_view(), name='admin_loan_repayment'),
    path('reject-loan/', views.RejectLoanApplication.as_view(), name='reject_loan'),
    path('request-loan-topup/', views.LoanTopUpRequestView.as_view(), name='loan_topup'),
    path('get-full-amount-payable/', views.FetchFullAmountPayable.as_view(), name='get_full_amount_payable'),

    path('loan-topup-applications/', views.LoanTopUpApprovalView.as_view(), name='loan_topup_applications'),
    path('approved-loan-topups/', views.LoanTopUpDisbursementView.as_view(), name='approved_loan_topups'),
    path('rejected-loan-topups/', views.RejectedTopUpRequests.as_view(), name='rejected_loan_topups'),
    path('disbursed-loan-topups/', views.DisbursedLoanTopUps.as_view(), name='disbursed_loan_topups'),

    path('approve-loan-topup/',views.LoanTopUpApprovalHandler.as_view(), name='approve_loan_topup'),
    path('disburse-loan-topup/', views.LoanTopUpDisbursementHandler.as_view(), name='disburse_loan_topup'),
    path('reject-loan-topup/', views.LoanTopUpRejectionHandler.as_view(), name='reject_loan_topup'),

    path('topup-details/<int:pk>/', views.FetchLoanAndTopUpDetails.as_view(), name='loan_topup_details'),
]