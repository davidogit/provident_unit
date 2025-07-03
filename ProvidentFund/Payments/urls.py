# payments/urls.py

from django.urls import path
from Payments.views.deposits import CreateTransactionView, verify_transaction
from Payments.views.withdrawals import WithdrawalView
from Payments.views.balance import GetBalanceView

urlpatterns = [
    path('deposit/<int:staff_id>/', CreateTransactionView.as_view(), name='create_transaction'),
    path('verify/<str:reference>/', verify_transaction, name='verify_transaction'),
    path('withdraw/<int:staff_id>/', WithdrawalView.as_view(), name='withdraw'),
    path('get-balance/<int:scheme_id>/<int:staff_id>/', GetBalanceView.as_view(), name='get_balance'),
]
