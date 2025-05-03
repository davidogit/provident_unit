from django.shortcuts import render
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.views.generic import ListView,CreateView,View,TemplateView
from .models import LoanApplication
from .forms import LoanForm
from django.utils.decorators import method_decorator
from Member.decorators import tenant_login_required,tenant_required
from Admin.decorators import role_required
from decimal import Decimal,ROUND_HALF_UP
import json
from django.views.decorators.csrf import csrf_exempt

# Create your views here.

class LoanApplicationView(TemplateView):
    template_name = 'loan_application.html'



class HandleLoanSubmission(View):
    def post(self, request, *args, **kwargs):
        print("Function Called")

        tenant = getattr(request, 'tenant', None)
        member = getattr(request.user, 'member', None)
        
        print(tenant , member)

        print("member.user: " , getattr(member, 'user',None))

        if not tenant or not member:
            return JsonResponse({
                'status':'error',
                'message': 'Missing tenant or member'
            })
        print("Function Called 1")

        form = LoanForm(request.POST)
        if form.is_valid():
            print("Function Called 2")
            form.instance.tenant = tenant
            form.instance.user = member
            form.instance.status = 'Pending'
            
            form.save()
            return JsonResponse({"status": "success", "message": "Loan application submitted."})
        else:
            return JsonResponse({"status": "error", "errors": form.errors}, status=400)

class LoanApprovalView(ListView):
    model = LoanApplication
    template_name = 'loan_approval.html'


class LoanDetails:
    def total_interest_flat(self, amount, tenure):
        p = Decimal(amount)
        r = Decimal('6.5')  # This can be made dynamic later
        t_months = Decimal(tenure)
        t_years = t_months / Decimal('12')

        return (p * r * t_years / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def loan_processing_fee_flat(self, amount):
        p = Decimal(amount)
        return (p * Decimal('0.015')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def total_payable_amount_flat(self, amount, tenure):
        return (Decimal(amount) + self.total_interest_flat(amount, tenure)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def disbursement_amount(self, amount):
        return (Decimal(amount) - self.loan_processing_fee_flat(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def calculate_monthly_installments_flat(self, amount, tenure):
        p = Decimal(amount)
        r = Decimal('6.5')
        t_months = Decimal(tenure)
        t_years = t_months / Decimal('12')

        total_interest = (p * r * t_years / Decimal('100'))
        total_amount_payable = p + total_interest
        monthly_emi = total_amount_payable / t_months

        return monthly_emi.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# Fetch Loan details to display upon application
class FetchLoanDetails(View):
    def get(self, *args, **kwargs):
        tenant = self.request.tenant
        potential_loan_amount_str = self.request.GET.get('amount')
        tenure_str = self.request.GET.get('tenure')

        if not tenant:
            return JsonResponse({
                'status':'error',
                'message':'Invalid request.'
            })
        
        # Fetch details
        if not potential_loan_amount_str and not tenure_str:
            return JsonResponse({
                'status':'error',
                'message':'Invalid parameters.'
            })
        
        try:
            amount = Decimal(potential_loan_amount_str)
            tenure = int(tenure_str)
        except ValueError:
            return JsonResponse({
                'status': 'error',
                'message': 'Amount and tenure must be valid numbers.'
            })
        
        # Instantiate class to get loan details
        loan_details = LoanDetails()

        return JsonResponse({
            'status':'success',
            'data':{
                'formatted_amount':amount,
                'interest_rate':6.5,
                'formatted_processing_fee':loan_details.loan_processing_fee_flat(amount),
                'formatted_total_repayment':loan_details.total_payable_amount_flat(amount,tenure),
                'formatted_monthly_installment':loan_details.calculate_monthly_installments_flat(amount,tenure),
                'formatted_disbursement_amount':loan_details.disbursement_amount(amount)
            }
        })


