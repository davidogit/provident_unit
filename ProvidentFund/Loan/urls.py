from django.urls import path
from . import views

urlpatterns = [
    path('<int:staff_id>/', views.LoanApplicationView.as_view(), name="loan_application"),
    path('calculate-details/',views.FetchLoanDetails.as_view()),
    path('apply/<int:staff_id>/', views.HandleLoanSubmission.as_view())
]