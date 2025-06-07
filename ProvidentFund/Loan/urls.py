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
    path('rejected-applications/', views.RejectedLoanApplications.as_view(), name='rejected_loans'),
    path('loan-types/', views.LoanTypeView.as_view(), name='loan_types'),
    path('add-loan-type/', views.CreateLoanType.as_view(),name='add_loan_type'),
    path('loan-type-details/<int:pk>/', views.LoanTypeDetail.as_view()),
    path('update-loan-type/<int:pk>/', views.LoanTypeUpdate.as_view()),
    path('delete-loan-type/<int:pk>/', views.LoanTypeDelete.as_view()),
    path('<int:staff_id>/loan_types/', views.MemberLoanTypeView.as_view(), name='member_loan_type'),
    path('fetch_loan_type_details/', views.FetchLoanTypeDetails.as_view(), name='fetch_loan_types'),
    path('<int:staff_id>/member-loan-details/<int:loan_id>/', views.MemberLoanDetailView.as_view(), name='member_loan_details'),
]