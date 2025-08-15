from datetime import timezone
from decimal import Decimal
import json
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from Admin.decorators import role_required
from django.db import transaction
import logging
from django.utils.decorators import method_decorator
from Member.decorators import tenant_required,tenant_login_required
from Admin.decorators import role_required
from django.core.exceptions import ObjectDoesNotExist
from contributions.models import Contribution, Membership, StaffAPI
from MultiScheme.models import InvestmentScheme, TenantEventNotification
from Member.models import Member,SchemeApproval, ExitApproval
from Payments.models import Transaction, WithdrawalRequest
from Member.tasks import notify_user_email_sms,notify_withdrawal_approval,send_otp_code,gen_send_email
from Payments.tasks import process_withdrawal_approval_workflow
from django.db.models import Sum,F
from django.views.generic import TemplateView,UpdateView,CreateView,ListView


logger = logging.getLogger(__name__)
@method_decorator(tenant_login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Member']), name='dispatch')
class WithdrawalView(TemplateView):
    template_name = 'Payments/withdrawal.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        context["schemes"] = InvestmentScheme.objects.filter(tenant=tenant, approved=True)
        return context
    
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            tenant = request.tenant
            member = request.user.member
            scheme_id = data.get('scheme_id')
            amount = data.get('amount')

            #  Validate inputs
            if not all([scheme_id, amount, member]):
                return JsonResponse({'status': 'error', 'message': 'Missing required fields.'}, status=400)

            amount = Decimal(amount)

            with transaction.atomic():
                #  Validate scheme and staff
                scheme = InvestmentScheme.objects.filter(tenant=tenant, id=scheme_id, approved=True).first()
                staff = StaffAPI.objects.filter(staff_number=member.staff_id).first()

                if not scheme or not staff:
                    return JsonResponse({'status': 'error', 'message': 'Invalid scheme or staff information.'}, status=400)

                # Create a withdrawal request
                withdrawal_request = WithdrawalRequest.objects.create(
                    tenant=tenant,
                    staff=staff,
                    scheme=scheme,
                    amount=amount,
                    request_date=timezone.now(),
                )
                logger.info(f" WithdrawalRequest created with ID: {withdrawal_request.id}")

                # Get all recipients for `withdrawal_request` event
                recipients = TenantEventNotification.objects.filter(
                    tenant=tenant,
                    event="withdrawal_request"
                ).values_list('staff__email', flat=True)  # Get list of emails

                if not recipients:
                    logger.warning(f"No recipients assigned for withdrawal_request event in tenant {tenant.id}")

                # Trigger Celery task to notify approvers
                transaction.on_commit(lambda: process_withdrawal_approval_workflow.delay(withdrawal_request.id))


                # Trigger Celery task to notify the user
                notify_user_email_sms.delay(
                    tenant_id=tenant.id,  
                    member_name=member.user.get_full_name(),
                    first_name=member.user.first_name,
                    last_name=member.user.last_name,
                    user_email=member.user.email,
                    tel_number=member.tel_number,
                    amount=amount,
                    scheme_name=scheme.name
                )

                return JsonResponse({
                    'status': 'success',
                    'message': 'Withdrawal request submitted for approval. Notifications sent to user and approvers.'
                })

        except Exception as e:
            logger.error(f"Unexpected error in WithdrawalView: {str(e)}")
            return JsonResponse({'status': 'error', 'message': 'An unexpected error occurred.'}, status=500)
        
