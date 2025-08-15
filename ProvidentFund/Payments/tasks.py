from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.db import transaction, models
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.db.models import Q, Sum
import logging
import requests
from datetime import timedelta
from decimal import Decimal
from typing import Dict, Any

from .models import Transaction, WithdrawalRequest
from .utils import PaystackAPI
from MultiScheme.models import TenantEventNotification, InvestmentScheme
from contributions.models import StaffAPI, Membership, Contribution
from Member.tasks import notify_user_email_sms

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def verify_payment_transaction(self, transaction_id: str) -> Dict[str, Any]:
    """
    Verify a payment transaction with Paystack API and update transaction status.
    
    Args:
        transaction_id (str): The ID of the transaction to verify
        
    Returns:
        dict: Result of the verification process
    """
    try:
        with transaction.atomic():
            # Use select_for_update to prevent race conditions
            transaction_obj = Transaction.objects.select_for_update().get(id=transaction_id)
            
            if transaction_obj.status == 'completed':
                logger.info(f"Transaction {transaction_id} already completed")
                return {'status': 'success', 'message': 'Transaction already completed'}
            
            # Verify with Paystack
            paystack_response = PaystackAPI.verify_transaction(transaction_obj.reference)
            
            if not paystack_response.get('status'):
                error_msg = paystack_response.get('message', 'Unknown API error')
                logger.error(f"Paystack API error for transaction {transaction_id}: {error_msg}")
                
                # If it's a configuration error, don't retry
                if 'configuration' in error_msg.lower():
                    transaction_obj.status = 'failed'
                    transaction_obj.save(update_fields=['status'])
                    return {'status': 'error', 'message': f'Configuration error: {error_msg}'}
                
                # For other API errors, let it retry
                raise Exception(f"API error: {error_msg}")
            
            data = paystack_response.get('data', {})
            
            # Check if payment was successful
            if data.get('status') == 'success':
                # Verify amount matches (convert to same currency/format)
                api_amount = Decimal(str(data.get('amount', 0))) / 100  # Paystack returns kobo
                if abs(api_amount - transaction_obj.amount) > Decimal('0.01'):
                    logger.error(f"Amount mismatch for transaction {transaction_id}: expected {transaction_obj.amount}, got {api_amount}")
                    transaction_obj.status = 'failed'
                    transaction_obj.save(update_fields=['status'])
                    return {'status': 'failed', 'message': 'Amount mismatch detected'}
                
                # Update transaction status
                transaction_obj.status = 'completed'
                transaction_obj.verified_at = timezone.now()
                transaction_obj.save(update_fields=['status', 'verified_at'])
                
                # Create a contribution record instead of manually updating balances
                # This leverages the optimized save method in the Contribution model
                contribution = Contribution.objects.create(
                    investment_scheme=transaction_obj.scheme,
                    member=transaction_obj.staff,
                    contribution_date=transaction_obj.transaction_date,
                    employee_amount=transaction_obj.amount,  # Assuming it's employee contribution
                    approved_contribution=True
                )
                
                # Send confirmation email asynchronously
                send_payment_confirmation_email.delay(transaction_id)
                
                logger.info(f"Transaction {transaction_id} verified and completed successfully")
                return {'status': 'success', 'message': 'Payment verified and completed'}
                
            elif data.get('status') == 'failed':
                # Payment failed
                transaction_obj.status = 'failed'
                transaction_obj.save(update_fields=['status'])
                logger.warning(f"Transaction {transaction_id} failed: {data.get('gateway_response', 'Unknown error')}")
                return {'status': 'failed', 'message': 'Payment verification failed'}
            else:
                # Payment still pending or other status
                logger.info(f"Transaction {transaction_id} still pending with status: {data.get('status')}")
                return {'status': 'pending', 'message': 'Payment still processing'}
                
    except Transaction.DoesNotExist:
        logger.error(f"Transaction {transaction_id} not found")
        return {'status': 'error', 'message': 'Transaction not found'}
    except Exception as e:
        logger.error(f"Error verifying transaction {transaction_id}: {str(e)}")
        # Retry the task with exponential backoff
        countdown = min(60 * (2 ** self.request.retries), 3600)  # Max 1 hour
        raise self.retry(exc=e, countdown=countdown)


@shared_task(bind=True, max_retries=3, default_retry_delay=600)
def process_failed_transactions(self) -> Dict[str, Any]:
    """
    Process failed transactions and attempt to retry them.
    This task runs periodically to handle failed payment transactions.
    """
    try:
        # Get failed transactions from the last 24 hours that haven't been retried recently
        cutoff_time = timezone.now() - timedelta(hours=24)
        retry_cutoff = timezone.now() - timedelta(hours=2)  # Don't retry too frequently
        
        failed_transactions = Transaction.objects.filter(
            status='failed',
            transaction_date__gte=cutoff_time,
            transaction_type='Deposit',
            updated_at__lt=retry_cutoff  # Ensure we don't retry too often
        ).select_related('staff', 'scheme')[:50]  # Limit batch size
        
        processed_count = 0
        success_count = 0
        
        for transaction_obj in failed_transactions:
            try:
                # Update the transaction to mark retry attempt
                transaction_obj.updated_at = timezone.now()
                transaction_obj.save(update_fields=['updated_at'])
                
                # Attempt to verify the transaction again
                result = verify_payment_transaction.delay(str(transaction_obj.id))
                processed_count += 1
                
                # Don't wait for result to avoid blocking, just schedule
                logger.info(f"Scheduled retry for failed transaction {transaction_obj.id}")
                
            except Exception as e:
                logger.error(f"Error scheduling retry for transaction {transaction_obj.id}: {str(e)}")
        
        logger.info(f"Scheduled retry for {processed_count} failed transactions")
        return {'status': 'success', 'processed_count': processed_count}
        
    except Exception as e:
        logger.error(f"Error in process_failed_transactions: {str(e)}")
        raise self.retry(exc=e, countdown=600)


@shared_task(bind=True, max_retries=2)
def send_payment_confirmation_email(self, transaction_id: str) -> Dict[str, Any]:
    """
    Send payment confirmation email to the user.
    
    Args:
        transaction_id (str): The ID of the transaction
    """
    try:
        transaction_obj = Transaction.objects.select_related(
            'staff', 'scheme', 'tenant'
        ).get(id=transaction_id)
        
        # Check if staff has email
        if not hasattr(transaction_obj.staff, 'email') or not transaction_obj.staff.email:
            logger.warning(f"No email found for staff in transaction {transaction_id}")
            return {'status': 'skipped', 'message': 'No email address found'}
        
        # Prepare email context
        context = {
            'transaction': transaction_obj,
            'staff': transaction_obj.staff,
            'scheme': transaction_obj.scheme,
            'amount': transaction_obj.amount,
            'date': transaction_obj.transaction_date,
            'reference': transaction_obj.reference,
            'tenant': transaction_obj.tenant
        }
        
        # Render email template
        subject = f"Payment Confirmation - {transaction_obj.reference}"
        
        try:
            html_message = render_to_string('Payments/email/payment_confirmation.html', context)
            plain_message = render_to_string('Payments/email/payment_confirmation.txt', context)
        except Exception as template_error:
            logger.error(f"Template rendering error for transaction {transaction_id}: {template_error}")
            # Fallback to simple text message
            plain_message = f"""
            Dear {transaction_obj.staff.first_name},
            
            Your payment of {transaction_obj.amount} has been confirmed.
            Transaction Reference: {transaction_obj.reference}
            Date: {transaction_obj.transaction_date}
            
            Thank you for your contribution.
            """
            html_message = None
        
        # Send email
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[transaction_obj.staff.email],
            html_message=html_message,
            fail_silently=False
        )
        
        logger.info(f"Payment confirmation email sent for transaction {transaction_id}")
        return {'status': 'success', 'message': 'Email sent successfully'}
        
    except Transaction.DoesNotExist:
        logger.error(f"Transaction {transaction_id} not found for email confirmation")
        return {'status': 'error', 'message': 'Transaction not found'}
    except Exception as e:
        logger.error(f"Error sending payment confirmation email for transaction {transaction_id}: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        return {'status': 'error', 'message': str(e)}


@shared_task(bind=True, max_retries=2)
def process_withdrawal_approval_workflow(self, withdrawal_request_id: str) -> Dict[str, Any]:
    """
    Process the withdrawal approval workflow and send notifications.
    
    Args:
        withdrawal_request_id (str): The ID of the withdrawal request
    """
    try:
        withdrawal_request = WithdrawalRequest.objects.select_related(
            'staff', 'scheme', 'tenant'
        ).get(id=withdrawal_request_id)
        
        # Get all recipients for withdrawal approval notifications
        recipients = TenantEventNotification.objects.filter(
            tenant=withdrawal_request.tenant,
            event="withdrawal_approval"
        ).select_related('staff').values_list('staff__email', flat=True)
        
        recipients = [email for email in recipients if email]  # Filter out empty emails
        
        if not recipients:
            logger.warning(f"No recipients found for withdrawal approval notifications for tenant {withdrawal_request.tenant.id}")
            return {'status': 'warning', 'message': 'No notification recipients found'}
        
        # Prepare email content
        subject = f"Withdrawal Request Approval Required - {withdrawal_request.id}"
        message = f"""
        A new withdrawal request requires your approval:
        
        Request ID: {withdrawal_request.id}
        Staff: {withdrawal_request.staff.first_name} {withdrawal_request.staff.last_name} ({withdrawal_request.staff.staff_number})
        Amount: ${withdrawal_request.amount:,.2f}
        Scheme: {withdrawal_request.scheme.name}
        Request Date: {withdrawal_request.request_date.strftime('%Y-%m-%d %H:%M')}
        
        Please review and approve/reject this request in the admin panel.
        """
        
        # Send notifications in batches to avoid overwhelming the email service
        batch_size = 10
        sent_count = 0
        failed_count = 0
        
        for i in range(0, len(recipients), batch_size):
            batch = recipients[i:i + batch_size]
            try:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=batch,
                    fail_silently=False
                )
                sent_count += len(batch)
            except Exception as e:
                failed_count += len(batch)
                logger.error(f"Failed to send approval notification batch: {str(e)}")
        
        logger.info(f"Withdrawal approval workflow processed for request {withdrawal_request_id}. Sent: {sent_count}, Failed: {failed_count}")
        return {
            'status': 'success', 
            'message': f'Notifications sent to {sent_count} recipients, {failed_count} failed'
        }
        
    except WithdrawalRequest.DoesNotExist:
        logger.error(f"Withdrawal request {withdrawal_request_id} not found")
        return {'status': 'error', 'message': 'Withdrawal request not found'}
    except Exception as e:
        logger.error(f"Error processing withdrawal approval workflow for {withdrawal_request_id}: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=300)
        return {'status': 'error', 'message': str(e)}


@shared_task(bind=True)
def cleanup_expired_transactions(self) -> Dict[str, Any]:
    """
    Clean up expired or stale transactions that are older than 30 days.
    This task helps maintain database performance and clean up old data.
    """
    try:
        # Get transactions older than 30 days with pending status
        cutoff_date = timezone.now() - timedelta(days=30)
        
        # Use bulk update for better performance
        expired_count = Transaction.objects.filter(
            status='pending',
            transaction_date__lt=cutoff_date
        ).update(
            status='expired',
            updated_at=timezone.now()
        )
        
        if expired_count > 0:
            logger.info(f"Marked {expired_count} expired transactions as expired")
        
        return {'status': 'success', 'processed_count': expired_count}
        
    except Exception as e:
        logger.error(f"Error in cleanup_expired_transactions: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task(bind=True)
def generate_monthly_payment_report(self, tenant_id: str, month: int = None, year: int = None) -> Dict[str, Any]:
    """
    Generate monthly payment report for a specific tenant.
    
    Args:
        tenant_id (str): The tenant ID
        month (int): Month number (1-12), defaults to current month
        year (int): Year, defaults to current year
    """
    try:
        if month is None:
            month = timezone.now().month
        if year is None:
            year = timezone.now().year
        
        # Get transactions for the specified month and year
        start_date = timezone.datetime(year, month, 1, tzinfo=timezone.get_current_timezone())
        if month == 12:
            end_date = timezone.datetime(year + 1, 1, 1, tzinfo=timezone.get_current_timezone())
        else:
            end_date = timezone.datetime(year, month + 1, 1, tzinfo=timezone.get_current_timezone())
        
        # Use single query with aggregation for better performance
        stats = Transaction.objects.filter(
            tenant_id=tenant_id,
            transaction_date__gte=start_date,
            transaction_date__lt=end_date
        ).aggregate(
            total_deposits=models.Sum(
                'amount',
                filter=Q(transaction_type='Deposit', status='completed')
            ),
            total_withdrawals=models.Sum(
                'amount',
                filter=Q(transaction_type='Withdrawal', status='completed')
            ),
            pending_count=models.Count(
                'id',
                filter=Q(status='pending')
            ),
            failed_count=models.Count(
                'id',
                filter=Q(status='failed')
            ),
            completed_count=models.Count(
                'id',
                filter=Q(status='completed')
            )
        )
        
        # Handle None values from aggregation
        total_deposits = stats['total_deposits'] or Decimal('0.00')
        total_withdrawals = stats['total_withdrawals'] or Decimal('0.00')
        
        # Generate report data
        report_data = {
            'tenant_id': tenant_id,
            'month': month,
            'year': year,
            'total_deposits': float(total_deposits),
            'total_withdrawals': float(total_withdrawals),
            'net_flow': float(total_deposits - total_withdrawals),
            'pending_transactions': stats['pending_count'],
            'failed_transactions': stats['failed_count'],
            'completed_transactions': stats['completed_count'],
            'total_transactions': sum([
                stats['pending_count'],
                stats['failed_count'], 
                stats['completed_count']
            ]),
            'generated_at': timezone.now().isoformat()
        }
        
        logger.info(f"Generated monthly payment report for tenant {tenant_id}, month {month}/{year}")
        return report_data
        
    except Exception as e:
        logger.error(f"Error generating monthly payment report for tenant {tenant_id}: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task(bind=True)
def monitor_payment_gateway_health(self) -> Dict[str, Any]:
    """
    Monitor the health of the payment gateway by making a test API call.
    This task runs periodically to ensure the payment service is operational.
    """
    try:
        # Use a lightweight health check instead of actual verification
        import requests
        response = requests.get(
            "https://api.paystack.co/transaction/verify/invalid_reference",
            headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
            timeout=10
        )
        
        # Even a 404 or error response means the API is reachable
        if response.status_code in [200, 400, 404]:
            logger.info("Payment gateway health check passed")
            return {
                'status': 'healthy', 
                'message': 'Payment gateway is operational',
                'response_time': response.elapsed.total_seconds()
            }
        else:
            logger.warning(f"Payment gateway health check returned status {response.status_code}")
            return {
                'status': 'unhealthy', 
                'message': f'Payment gateway returned status {response.status_code}'
            }
            
    except requests.exceptions.Timeout:
        logger.error("Payment gateway health check timed out")
        return {'status': 'timeout', 'message': 'Payment gateway request timed out'}
    except Exception as e:
        logger.error(f"Payment gateway health check error: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task(bind=True, max_retries=2)
def retry_pending_transactions(self) -> Dict[str, Any]:
    """
    Retry pending transactions that may have been stuck in the system.
    This task helps recover from temporary payment gateway issues.
    """
    try:
        # Get pending transactions older than 2 hours but newer than 24 hours
        old_cutoff = timezone.now() - timedelta(hours=24)
        recent_cutoff = timezone.now() - timedelta(hours=2)
        
        pending_transactions = Transaction.objects.filter(
            status='pending',
            transaction_date__gte=old_cutoff,
            transaction_date__lt=recent_cutoff,
            transaction_type='Deposit'
        ).select_related('staff', 'scheme')[:20]  # Limit batch size
        
        retry_count = 0
        for transaction_obj in pending_transactions:
            try:
                # Schedule verification instead of doing it synchronously
                verify_payment_transaction.delay(str(transaction_obj.id))
                retry_count += 1
                logger.info(f"Scheduled verification for pending transaction {transaction_obj.id}")
            except Exception as e:
                logger.error(f"Error scheduling verification for pending transaction {transaction_obj.id}: {str(e)}")
        
        logger.info(f"Scheduled verification for {retry_count} pending transactions")
        return {'status': 'success', 'retry_count': retry_count}
        
    except Exception as e:
        logger.error(f"Error in retry_pending_transactions: {str(e)}")
        return {'status': 'error', 'message': str(e)}