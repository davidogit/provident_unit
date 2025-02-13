from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns =[
    path('', views.LandingPage.as_view(), name='landing_page'),
    path('dashboard', views.Invest.as_view(), name='finance_page'),
    path('<int:scheme_name>/addInvestment/', views.AddInvestment.as_view(), name='add_investment'),
    path('<int:scheme_name>/investmentList/', views.InvestmentListView.as_view(), name='investment_list'),
    path('<int:scheme_name>/memberList/', views.MemberListView.as_view(), name='member_list'),
    path('<int:scheme_name>/<int:pk>/', views.MemberDetailView.as_view(), name='member_detail'),
    path('<int:scheme_name>/investmentDetail/<int:pk>/', views.InvestmentDetailView.as_view(), name='investment_detail'),
    path('<int:scheme_name>/ivestment_approval/', views.ApproveMaturedInvestment.as_view(), name='investment_approval'),
    path('<int:scheme_name>/approved_investments/', views.ApprovedInvestments.as_view(), name='approved_investments'),
    
    path('<int:scheme_name>/update/<int:pk>', views.InvestmentUpdateView.as_view(), name='investment_update'),
    path('<int:scheme_name>/deleteInvestment/<int:pk>/', views.InvestmentDeleteView.as_view(), name='delete_investment'),
    path('<int:scheme_name>/investmentRollover/<int:pk>/', views.RolloverInvestment.as_view(), name='rollover_percentage'),
    path('<int:scheme_name>/investment_query/', views.InvestmentQuery.as_view(), name='query'),

    # Member URLS
    # path('<int:scheme_name>/memberUpdate/<int:pk>/', views.MemberUpdateView.as_view(), name='member_update'),
    # path('<int:scheme_name>/deleteMember/<int:pk>/', views.MemberDeleteView.as_view(), name='delete_member'),
    path('<int:scheme_name>/exited-members/', views.ExitedMembers.as_view(), name='exited_members'),

    # Bank Interest Related URLS
    # path('<int:scheme_name>/add_bank_interest/', views.BankInterestCreateView.as_view(), name='add_bank_interest'),
    # path('<int:scheme_name>/bank_interest_list/', views.BankInterestListView.as_view(), name='bank_interest_list'),
    # path('<int:scheme_name>/bank-interest-query/', views.BankInterestQuery.as_view(), name='bank_interest_query'),

    #Delayed Interest Related URLS 
    # path('<int:scheme_name>/add_delayed_interest/', views.DelayedInterestCreateView.as_view(), name='add_delayed_interest'),
    path('<int:scheme_name>/delayed_interest_list/', views.DelayedInterestListView.as_view(), name='delayed_interest_list'),
    path('<int:scheme_name>/delayed-interest-query/', views.DelayedInterestQuery.as_view(), name='delayed_interest_query'),

    # OTHERS
    path('access_denied/', views.AccessDenied.as_view(), name='access_denied'),

    # Scheme Approval
    path('approvals/', views.SchemeApplications.as_view(), name='scheme_approval'),

    # History of investments
    path('recent_activities/', views.RecentActivities.as_view(), name='recent_activities'),

    # contribution approval
    path('<int:scheme_name>/approve-contributions/', views.ApproveContributions.as_view(), name='approve_contributions'),

    # Endpoint for contribution data fetch
    path('<int:scheme_name>/fetch_contributions/', views.FetchContributions.as_view(), name='fetch-contributions'),

    # Exit Meber approval url
    path('exiting_members/', views.ApproveExitedMembers.as_view(), name='approve_exit_members'),


    # Mass Member Upload
    path('mass_upload/', views.MassMemberUpload.as_view(), name='mass_enroll'),


    # Payout URLs
    path('general-payout/', views.GeneralPayoutView.as_view(), name='general_payout'),
    path('fetch-members/', views.FetchWithdrawalRequests.as_view(), name='fetch-members'),
    # payment History
    path('payment-history/', views.PaymentHistoryView.as_view(), name='payment_history'),
    # Level 2 withdrawal request approval
    path('approve-batch-withdrawal/', views.SecondPhaseOfWithdrawalApproval.as_view(), name='second_withdrawal_approval'),
    # Level 2 Email approval of withdrawals
    path('email-batch-approval/<slug:batch_id>/<scheme_id>/', views.SecondPhaseOfWithdrawalApprovalEmail.as_view(),name='email_withdrawal_approval'),
    # Batch withdrawals list view
    path('batch-withdrawal-list/<slug:batch_id>/', views.BatchWithdrawalListView.as_view(), name='batch_withdrawal_list'),
    # Final batch Withdrawal approval
    path('final-batch-approval/', views.FinalBatchWithdrawalApproval.as_view(), name='final_batch_withdrawal_approval'),

    # Schedule Payment Date URL
    path('schedule_payment_dates/', views.SchedulePaymentDateView.as_view(), name='schedule_payment_date'),
    # delete scheduled date
    path('delete_scheduled_date/<int:pk>/', views.DeleteSchedulePaymentDate.as_view(), name='delete_scheduled_dates'),
    # Approve scheduled date
    path('approve-payout-date/<int:date_id>/', views.ApproveScheduledPaymentDateView.as_view(), name='approve_scheduled_date'),
    # Pause scheduled date
    path('pause-payout-date/<int:schedule_date_id>/', views.PauseScheduledPaymentDateView.as_view(), name='pause_scheduled_date'),

    # SUPPLIER URL
    path('suppliers/', views.SupplierView.as_view(), name='supplier_view'),

    # Delete supplier
    path('delete-supplier/<int:pk>/', views.DeleteSupplierView.as_view(), name='delete_supplier'),
    # Update supplier
    path('update-supplier/<int:pk>/', views.UpdateSupplierView.as_view(), name='update_supplier'),

    # REQUISITION URL
    path('create-requisition/', views.RaiseRequisitionView.as_view(), name='raise_requisition'),
    # delete requisition
    path('delete-requisition/<int:pk>/', views.DeleteRequisitionView.as_view(), name='delete_requisition'),
    # delete requisition item
    path('delete-requisition-item/<int:pk>/<int:req_id>/', views.DeleteRequisitionItemView.as_view(), name='delete_requisition_item'),
    # Add requisition item
    path('add-requisition-item/', views.AddRequisitionItemView.as_view(), name='add_requisition_item'),
    # Approve requisition
    path('approve-requisition/<int:req_id>/', views.ApproveRequisitionView.as_view(), name='approve_requisition'),
    #fetch requisition items
    path('get-requisition-items/<int:req_id>/', views.FetchItemsView.as_view(), name='fetch_items'),


    # PURCHASE ORDER URL
    path('purchase-orders/', views.PurschaseOrderView.as_view(), name='purchase_order'),
    # received order
    path('received-order/<slug:order_id>/', views.PurschaseOrderView.as_view(), name='receive-order'),
    #fetch order items
    path('get-order-items/<slug:order_id>/', views.FetchPurchaseOrderView.as_view(), name='fetch_order_items'),

    # PAYOUT INVOICE URL
    path('payout-invoice/', views.PayoutInvoiceView.as_view(), name='payout_invoice'),
    
    # EVENT MAPPING
    path('event_mapping/', views.EventMapping.as_view(), name='event_mapping')
]