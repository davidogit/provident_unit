import json
import uuid
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views import View
from django.utils.decorators import method_decorator
import requests
from Admin.decorators import role_required
from django.db import transaction
import logging
from django.utils.decorators import method_decorator
from Member.decorators import tenant_required,tenant_login_required
from Admin.decorators import role_required
from django.core.exceptions import ObjectDoesNotExist
from contributions.models import Contribution, Membership, StaffAPI
from MultiScheme.models import InvestmentScheme, TenantEventNotification
from decimal import Decimal
from Member.models import Member,SchemeApproval, Transaction,ExitApproval,WithdrawalRequest
from Member.tasks import notify_user_email_sms,notify_withdrawal_approval,send_otp_code,gen_send_email
from django.db.models import Sum,F
from django.views.generic import TemplateView,UpdateView,CreateView,ListView
from django.views.decorators.http import require_GET
from Payments.utils import PaystackAPI


logger = logging.getLogger(__name__)
@method_decorator(tenant_login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Member']), name='dispatch')
class CreateTransactionView(View):
    template_name = 'Payments/create_transaction.html'

    def get(self, request, *args, **kwargs):
        tenant = request.tenant
        schemes = InvestmentScheme.objects.filter(tenant=tenant,approved=True)
        reference = str(uuid.uuid4())  # Pre-generate a unique reference

        context = {
            'schemes': schemes,
            'PAYSTACK_PUBLIC_KEY': settings.PAYSTACK_PUBLIC_KEY,
            'reference': reference,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            tenant = request.tenant
            staff_id = kwargs.get('staff_id')
            scheme_id = data.get('scheme_id')
            amount = data.get('amount')
            email = data.get('email')
            reference = data.get('reference')

            if not all([scheme_id, amount, email, reference]):
                return JsonResponse({'status': 'error', 'message': 'Missing required fields.'}, status=400)

            with transaction.atomic():
                scheme = InvestmentScheme.objects.get(tenant=tenant, id=scheme_id, approved=True)
                staff = StaffAPI.objects.get(staff_number=staff_id)

                if Transaction.objects.filter(reference=reference).exists():
                    return JsonResponse({'status': 'error', 'message': 'Duplicate reference detected.'}, status=400)

                amount_in_kobo = int(float(amount) * 100)
                transaction_obj = Transaction.objects.create(
                    tenant=tenant,
                    staff=staff,
                    # member=member,
                    scheme=scheme,
                    amount=amount,
                    reference=reference
                )

                staff.contributions = F('contributions') + amount
                staff.save(update_fields=['contributions'])

                history_url = reverse('transaction_history', kwargs={
                    'tenant_id': tenant.id,
                    'staff_id':  staff.staff_number
                })

                return JsonResponse({
                    'status': 'success',
                    'transaction_reference': transaction_obj.reference,
                    'amount': amount_in_kobo,
                    'email': email,
                    'redirect_url': history_url
                })

        except json.JSONDecodeError:
            logger.error("Invalid JSON in request body")
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON in request body'}, status=400)
        except InvestmentScheme.DoesNotExist:
            logger.error(f"Invalid scheme ID: {scheme_id}")
            return JsonResponse({'status': 'error', 'message': 'Invalid scheme ID.'}, status=400)
        except StaffAPI.DoesNotExist:
            logger.error(f"Staff not found for member: {staff_id}")
            return JsonResponse({'status': 'error', 'message': 'Staff not found.'}, status=400)
        except Exception as e:
            logger.error(f"Unexpected error in CreateTransactionView: {str(e)}")
            return JsonResponse({'status': 'error', 'message': 'An unexpected error occurred.'}, status=500)

    @staticmethod
    def verify_transaction(reference):
        return PaystackAPI.verify_transaction(reference)

from Payments.utils import PaystackAPI

@require_GET
def verify_transaction(request, reference):
    try:
        response = PaystackAPI.verify_transaction(reference)
    except Exception as e:
        pass
