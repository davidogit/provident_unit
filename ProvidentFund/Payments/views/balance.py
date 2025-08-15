from decimal import Decimal
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
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
from django.db.models import Sum,F,Q
from django.views.generic import TemplateView,UpdateView,CreateView,ListView


logger = logging.getLogger(__name__)

@method_decorator(tenant_login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Member']), name='dispatch')
class GetBalanceView(View):
    def get(self, request, *args, **kwargs):
        scheme_id = self.kwargs["scheme_id"]
        staff_id = self.kwargs["staff_id"]
        tenant = self.request.tenant
        try:
            staff = StaffAPI.objects.get(staff_number=int(staff_id), tenant=tenant)
        except ObjectDoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Staff not found'}, status=404)
        print("tenant:",tenant)
       
        try:
        # Fetch the investment scheme
            scheme = InvestmentScheme.objects.get(id=scheme_id, tenant=tenant,approved=True)

        except ObjectDoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Investment scheme not found.'})
        
        except Exception as e:
            logger.error(f"Error in GetBalanceView: {str(e)}")
            return JsonResponse({'status': 'error', 'message': 'An error occured'})
        try:
        
            # Validate if the staff_id matches a valid Membership
            membership = Membership.objects.filter(
                tenant=tenant,
                scheme=scheme,
                staff=staff
            ).first()
            print("staff_id:",staff)
        except ObjectDoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Membership not found.'})
        
        except Exception as e:
            logger.error(f"Error in GetBalanceView: {str(e)}")
            return JsonResponse({'status': 'error', 'message': 'An error occured'})
        

        # Calculate the available balance
        available_balance = membership.total_earnings

        return JsonResponse({
            'status': 'success',
            'balance': Decimal(available_balance)
        })
