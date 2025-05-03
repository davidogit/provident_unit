from django.urls import path
from . import views

urlpatterns = [
    path('', views.LoanApplicationView.as_view(), name="loan_application"),
]