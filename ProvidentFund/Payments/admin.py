from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count
from django.db import models
from Payments.models import Transaction, WithdrawalRequest
from Payments.tasks import (
    verify_payment_transaction, 
    process_failed_transactions,
    cleanup_expired_transactions,
    retry_pending_transactions,
    monitor_payment_gateway_health
)

class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'transaction_type', 'amount', 'status', 'staff', 
        'scheme', 'transaction_date', 'payment_method', 'reference'
    ]
    list_filter = ['status', 'transaction_type', 'payment_method', 'transaction_date', 'tenant']
    search_fields = ['id', 'reference', 'staff__staff_number', 'staff__email']
    readonly_fields = ['id', 'transaction_date']
    date_hierarchy = 'transaction_date'
    
    actions = ['verify_selected_transactions', 'retry_failed_transactions', 'cleanup_expired_transactions']
    
    def verify_selected_transactions(self, request, queryset):
        """Verify selected transactions using Paystack API"""
        count = 0
        for transaction in queryset.filter(status='pending'):
            try:
                result = verify_payment_transaction.delay(transaction.id)
                count += 1
            except Exception as e:
                messages.error(request, f"Error verifying transaction {transaction.id}: {str(e)}")
        
        if count > 0:
            messages.success(request, f"Started verification for {count} transactions")
        else:
            messages.warning(request, "No pending transactions selected for verification")
    
    verify_selected_transactions.short_description = "Verify selected transactions"
    
    def retry_failed_transactions(self, request, queryset):
        """Retry failed transactions"""
        failed_transactions = queryset.filter(status='failed')
        count = failed_transactions.count()
        
        if count > 0:
            process_failed_transactions.delay()
            messages.success(request, f"Started retry process for {count} failed transactions")
        else:
            messages.warning(request, "No failed transactions selected")
    
    retry_failed_transactions.short_description = "Retry failed transactions"
    
    def cleanup_expired_transactions(self, request, queryset):
        """Clean up expired transactions"""
        cleanup_expired_transactions.delay()
        messages.success(request, "Started cleanup of expired transactions")
    
    cleanup_expired_transactions.short_description = "Clean up expired transactions"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('staff', 'scheme', 'tenant')
    
    def get_list_display(self, request):
        """Add summary statistics to the changelist view"""
        return super().get_list_display(request)
    
    def changelist_view(self, request, extra_context=None):
        """Add summary statistics to the changelist view"""
        response = super().changelist_view(request, extra_context=extra_context)
        
        try:
            qs = response.context_data['cl'].queryset
            stats = {
                'total_transactions': qs.count(),
                'total_amount': qs.filter(status='completed').aggregate(total=Sum('amount'))['total'] or 0,
                'pending_count': qs.filter(status='pending').count(),
                'failed_count': qs.filter(status='failed').count(),
                'completed_count': qs.filter(status='completed').count(),
            }
            response.context_data['stats'] = stats
        except (AttributeError, KeyError):
            pass
        
        return response

class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'staff', 'scheme', 'amount', 'request_date', 
        'approval_status', 'tenant'
    ]
    list_filter = ['first_approval', 'second_approval', 'third_approval', 'fourth_approval', 'request_date', 'tenant']
    search_fields = ['id', 'staff__staff_number', 'staff__email']
    readonly_fields = ['id', 'request_date']
    date_hierarchy = 'request_date'
    
    def approval_status(self, obj):
        """Display approval status as a colored indicator"""
        if obj.fourth_approval:
            return format_html('<span style="color: green;">✓ Fully Approved</span>')
        elif obj.third_approval:
            return format_html('<span style="color: orange;">✓ Third Level</span>')
        elif obj.second_approval:
            return format_html('<span style="color: orange;">✓ Second Level</span>')
        elif obj.first_approval:
            return format_html('<span style="color: orange;">✓ First Level</span>')
        else:
            return format_html('<span style="color: red;">⏳ Pending</span>')
    
    approval_status.short_description = 'Approval Status'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('staff', 'scheme', 'tenant')

# Register the models with custom admin classes
admin.site.register(Transaction, TransactionAdmin)
admin.site.register(WithdrawalRequest, WithdrawalRequestAdmin)
