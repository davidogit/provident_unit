import datetime

from django.db import IntegrityError
from django.db.models import Sum, DecimalField
from django.forms import model_to_dict
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.http import JsonResponse
from django.views.generic import ListView,CreateView,View,TemplateView,DetailView,UpdateView,DeleteView
from pyexpat.errors import messages

from .models import LoanApplication, LoanRepayment, LoanType, LoanAmortizationSchedule
from .forms import LoanForm,LoanTypeForm
from django.utils.decorators import method_decorator
from Member.decorators import tenant_login_required,tenant_required
from Admin.decorators import role_required
from decimal import Decimal,ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.utils import timezone


# Create your views here.

class LoanApplicationView(TemplateView):
    template_name = 'loan_application.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        loan_type_id = self.request.GET.get('loan_type')

        if not tenant or not loan_type_id:
            return context

        loan_type = LoanType.objects.filter(
            tenant=tenant,
            id=loan_type_id
        ).first()

        if loan_type:
            context['loan_type'] = loan_type

        return context


class LoanTypeView(ListView):
    model = LoanType
    template_name = 'loan_types.html'
    context_object_name = 'loan_types'
    paginate_by = 10

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            return self.model.objects.filter(
                tenant=tenant
            ).order_by('-created_at')
        return super().get_queryset().none()



class CreateLoanType(CreateView):
    model = LoanType
    form_class = LoanTypeForm

    def form_valid(self, form):
        tenant = getattr(self.request, 'tenant', None)

        if tenant:
            form.instance.tenant = tenant
            self.object = form.save()
            return JsonResponse({
                'status':'success',
                'redirect_url':self.get_success_url()
            })
        return JsonResponse({
            'status':'error',
            'message':'Unauthorized or invalid tenant.'
        })

    def form_invalid(self, form):
        return JsonResponse({
            'status':'error',
            'message':form.errors.get_json_data()
        })

    def get_success_url(self):
        tenant = getattr(self.request, 'tenant',None)

        return reverse('loan_types',kwargs={'tenant_id':tenant.id})


"""
UPDATE VIEW FOR LOAN TYPE
"""
class LoanTypeUpdate(UpdateView):
    model = LoanType
    form_class = LoanTypeForm

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            return self.model.objects.filter(
                tenant=tenant
            )
        return super().get_queryset().none()

    def form_valid(self, form):
        tenant = getattr(self.request, 'tenant', None)

        if tenant and form.instance.tenant == tenant:
            self.object = form.save()
            return JsonResponse({
                'status': 'success',
                'message': 'Loan type updated successfully.'
            })

        return JsonResponse({
            'status': 'error',
            'message': 'Unauthorized or invalid tenant.'
        }, status=403)

    def form_invalid(self, form):
        return JsonResponse({
            'status': 'error',
            'errors': form.errors.get_json_data()
        }, status=400)

    def get_success_url(self):
        tenant = getattr(self.request, 'tenant', None)
        return reverse('loan_types', kwargs={'tenant_id': tenant.id})


"""
DELETE VIEW FOR LOAN TYPE
"""
class LoanTypeDelete(DeleteView):
    model = LoanType

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            return super().get_queryset().filter(tenant=tenant)
        return LoanType.objects.none()

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        if self.object.loan_applications.all():
            return JsonResponse({
                'status':'error',
                'message': 'Cannot delete this loan type as it is still referenced by existing loan applications.'
            })
        
        self.object.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Loan type deleted successfully.',
            'redirect_url': self.get_success_url()
        })

    def get_success_url(self):
        tenant = getattr(self.request, 'tenant', None)
        return reverse('loan_types', kwargs={'tenant_id': tenant.id})



"""
DETAIL VIEW FOR LOAN TYPE
"""
class LoanTypeDetail(DetailView):
    model = LoanType

    def get(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)

        loan_type = self.get_object()

        if(tenant and loan_type.tenant != tenant):
            return JsonResponse({
                'status':'error',
                'message':'Invalid request - Access denied'
            }, status=403)
        
        data = model_to_dict(
            loan_type,
            exclude=['created_at']
        )

        return JsonResponse({
            'status':'success',
            'data':data
        })

class HandleLoanSubmission(View):
    def post(self, request, *args, **kwargs):
        print("Function Called")

        tenant = getattr(request, 'tenant', None)
        member = getattr(request.user, 'member', None)
        loan_type_id = self.request.POST.get('loan_type_id')

        if not tenant or not member:
            return JsonResponse({
                'status':'error',
                'message': 'Missing tenant or member'
            })
        

        # check for existing loan type
        loan_type = None
        if loan_type_id:
            loan_type = LoanType.objects.filter(
                tenant=tenant,
                id=loan_type_id
            ).first()
        

        if not loan_type:
            return JsonResponse({
                'status':'error',
                'message':'Could not find specified loan type.'
            })
        
        # Eligibility Logic
        #TODO ensure min and max amount

        form = LoanForm(request.POST)
        if form.is_valid():
            print("Function Called 2")
            form.instance.tenant = tenant
            form.instance.user = member
            form.instance.status = 'Pending'
            form.instance.loan_type = loan_type
            
            try:
                form.save()
                return JsonResponse({"status": "success", "message": "Loan application submitted."})
            except Exception as e:
                return JsonResponse({
                    'status':'error',
                    'message':f'{e}'
                })

        else:
            return JsonResponse({"status": "error", "errors": form.errors}, status=400)




"""
CLASS TO CALCULATE AND DISPLAY EMI TO MEMBER
"""
class LoanDetails:
    def __init__(self, principal, tenure_months, loan_type):
        self.principal = Decimal(principal)
        self.tenure_months = Decimal(tenure_months)
        self.tenure_years = self.tenure_months / Decimal('12')
        self.loan_type = loan_type

        self.annual_rate = Decimal(loan_type.loan_interest_rate)
        self.monthly_rate = self.annual_rate / Decimal('1200')
        self.processing_fee_percent = Decimal(loan_type.loan_fee_percentage)
        self.interest_calc_type = loan_type.interest_calculation_type.upper()  # "FLAT" or "REDUCING"

    def total_interest_flat(self):
        total_interest = (self.principal * self.annual_rate * self.tenure_years) / Decimal('100')
        return total_interest.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def loan_processing_fee(self):
        fee_decimal = self.processing_fee_percent / Decimal('100')
        processing_fee = self.principal * fee_decimal
        return processing_fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def total_payable_amount_flat(self):
        return (self.principal + self.total_interest_flat()).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def disbursement_amount(self):
        return (self.principal - self.loan_processing_fee()).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def calculate_monthly_emi(self):
        if self.interest_calc_type == 'FLAT':
            total_interest = self.total_interest_flat()
            total_payable = self.principal + total_interest
            emi = total_payable / self.tenure_months

        elif self.interest_calc_type == 'REDUCING':
            r = self.monthly_rate
            T = self.tenure_months
            P = self.principal

            if r == 0:
                emi = P / T
            else:
                numerator = P * r * (1 + r) ** T
                denominator = ((1 + r) ** T) - 1
                emi = numerator / denominator

        else:
            raise ValueError("Invalid interest calculation type.")

        return emi.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def estimate_total_interest(self):
        if self.interest_calc_type == 'FLAT':
            return self.total_interest_flat()
        elif self.interest_calc_type == 'REDUCING':
            remaining_balance = self.principal
            total_interest = Decimal('0.00')
            emi = self.calculate_monthly_emi()

            for _ in range(int(self.tenure_months)):
                interest_component = (remaining_balance * self.monthly_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                total_interest += interest_component
                principal_component = emi - interest_component
                remaining_balance -= principal_component
                if remaining_balance <= 0:
                    break

            return total_interest.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            raise ValueError("Invalid interest calculation type.")



"""
This View is to use user entered amount to calculate loan
before user proceeds to apply
"""
# Fetch Loan details to display upon application
class CalculatePotentialLoan(View):
    def get(self, *args, **kwargs):
        tenant = self.request.tenant
        potential_loan_amount_str = self.request.GET.get('amount')
        tenure_str = self.request.GET.get('tenure')
        loan_type_id = self.request.GET.get('loan_type_id')

        if not tenant:
            return JsonResponse({
                'status':'error',
                'message':'Invalid request.'
            })

        if not loan_type_id:
            return JsonResponse({
                'status':'error',
                'message':'Invalid request. Missing loan type ID.'
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

        # Fetch Loan Type
        loan_type = LoanType.objects.filter(
            tenant=tenant,
            id=loan_type_id
        ).first()

        if not loan_type:
            return JsonResponse({
                'status':'error',
                'message':'Could not find specified loan type.'
            })
        
        # Instantiate class to get loan details
        loan_details = LoanDetails(
            principal=amount,
            tenure_months=tenure,
            loan_type=loan_type
        )

        try:
            processing_fee = loan_details.loan_processing_fee()
            total_repayment = loan_details.total_payable_amount_flat()
            monthly_installment = loan_details.calculate_monthly_emi()
            disbursement_amount = loan_details.disbursement_amount()
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message':f'Error calculating loan details: {e}'
            })

        return JsonResponse({
            'status':'success',
            'data':{
                'formatted_amount':amount,
                'interest_rate':loan_type.loan_interest_rate,
                'formatted_processing_fee':processing_fee,
                'formatted_total_repayment':total_repayment,
                'formatted_monthly_installment':monthly_installment,
                'formatted_disbursement_amount':disbursement_amount,
            }
        })


"""
MEMBER VIEW TO TRACK LOANS
"""
# Page for member to view and track loan details
class MemberLoanPage(ListView):
    model = LoanApplication
    paginate_by = 5
    template_name = 'member_loan_page.html'
    context_object_name = 'loans'
    

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        member = getattr(self.request.user, 'member', None)
        print("Tenant: ", tenant , "Member: ", member)
        if tenant and member:
            loans = self.model.objects.filter(
                tenant=tenant,
                user=member,
                approved=True,
                disbursed=True
            )
            print("List of Loans: ", loans)
            return loans
        return super().get_queryset().none()


"""
PAGE TO DISPLAY ALL LOAN TYPES TO MEMBERS
"""
class MemberLoanTypeView(ListView):
    model = LoanType
    template_name = 'member_loan_type_page.html'
    paginate_by = 9
    context_object_name = 'loan_types'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)

        if tenant:
            return self.model.objects.filter(
                tenant=tenant
            )
        
        return self.model.objects.none()


"""
VIEW TO FETCH LOAN TYPE DETAILS
"""
class FetchLoanTypeDetails(View):
    def get(self,*args,**kwargs):
        tenant = getattr(self.request, 'tenant', None)
        loan_type_id = self.request.GET.get("loan_type_id")

        print(f"Fetching Loan Type Details for {loan_type_id} and {tenant}")

        if not tenant:
            return JsonResponse({
                'status':'error',
                'message':'Invalid request. Missing Tenant.'
            })
        if not loan_type_id:
            return JsonResponse({
                'status':'error',
                'message':'Invalid request. Missing loan type ID.'
            })
        
        loan_type = LoanType.objects.filter(
            tenant=tenant,
            id=loan_type_id
        ).first()

        return JsonResponse({
            'status':'success',
            'data':{
                'name':loan_type.name,
                'description':loan_type.description,
                'requires_membership':loan_type.requires_membership,
                'loan_interest_rate':loan_type.loan_interest_rate,
                'interest_calculation_type':loan_type.interest_calculation_type,
                'loan_fee_percentage':loan_type.loan_fee_percentage,
                'min_amount':loan_type.min_amount,
                'max_amount':loan_type.max_amount,
                'late_payment_penalty':loan_type.late_payment_penalty,
                'minimum_year':loan_type.minimum_year,
                'minimum_contribution_amount':loan_type.minimum_contribution_amount

            }
        })

"""
LOAN APPROVAL VIEW
"""
class LoanApprovalView(ListView):
    model = LoanApplication
    template_name = 'loan_approval_base.html'
    paginate_by = 20
    context_object_name = 'loan_applications'

    def get_queryset(self):
        tenant = self.request.tenant

        if tenant:
            return self.model.objects.filter(
                tenant=tenant,
                approved=False,
                status = "PENDING"
            ).order_by("-application_date")
        return LoanApplication.objects.none()
    
    def post(self,request,*args,**kwargs):
        loan_id = self.request.POST.get("loan_id")
        tenant = self.request.tenant
        user = self.request.user

        if not tenant:
            return JsonResponse({
                'status':'error',
                'message':'Invalid request'
            })
        
        if not loan_id:
            return JsonResponse({
                'status':'error',
                'message':'Please select a loan to approve.'
            })
        
        # get loan and approve
        loan = self.get_queryset().filter(
            id=loan_id
        ).first()

        if loan:
            try:
                loan.approve_loan(user)
                return JsonResponse({
                    'status':'success',
                    'message':'Loan approved successfully.'
                })
            except Exception as e:
                return JsonResponse({
                    'status':'error',
                    'message':f'Failed to approve loan: {e}'
                })
        return JsonResponse({
            'status':'error',
            'message':'Couldn\'t find loan to approve.'
        })

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant',None)

        context.update(loan_count_metrics(tenant,status='pending'))
        return context


"""
APPROVED LOANS AND DISBURSEMENT FUNCTIONALITIES
"""
class DisburseApprovedLoans(ListView):
    model = LoanApplication
    template_name = 'approved_loan.html'
    context_object_name = 'approved_loans'

    def get_queryset(self):
        tenant = getattr(self.request,'tenant',None)
        if tenant:
            # Get loan approved loan applications to be disbursed
            return self.model.objects.filter(
                tenant=tenant,
                approved=True,
                status='APPROVED',
                disbursed=False,
                rejected=False
            ).order_by(
                '-approval_date'
            )
        return self.model.objects.none()

    """
    HANDLE DISBURSEMENT OPERATION
    """
    # TODO: HANDLE DISBURSEMENT LOGIC
    def post(self,*args,**kwargs):
        tenant = getattr(self.request,'tenant',None)
        user = getattr(self.request.user,'user',None)
        # loan details
        loan_id = int(self.request.POST.get('loan_id'))

        if not tenant:
            return JsonResponse({
                'status':'error',
                'message':'Invalid request.'
            })

        if not loan_id:
            return JsonResponse({
                'status':'error',
                'message':'Loan ID is required.'
            })

        # get loan object
        loan = self.get_queryset().filter(
            id=loan_id
        ).first()

        if not loan:
            return JsonResponse({
                'status':'error',
                'message':'Loan not found.'
            })

        # Check if the loan is already disbursed
        if loan.disbursed:
            return JsonResponse({
                'status':'error',
                'message':'Loan has already been disbursed.'
            })

        # disburse the loan
        try:
            loan.disburse_loan(user)
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message':f'Error disbursing loan: {e}'
            })

        return JsonResponse({
            'status':'success',
            'message':'Loan disbursed successfully.'
        })



    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant',None)
        
        context.update(loan_count_metrics(tenant,status='approved'))
        return context


"""
DISBURSED LOANS LIST VIEW
"""
class DisbursedLoans(ListView):
    model = LoanApplication
    paginate_by = 10
    template_name = "disbursed_loans.html"
    context_object_name = 'disbursed_loans'

    def get_queryset(self):
        tenant = getattr(self.request,'tenant',None)

        if not tenant:
            return self.model.objects.none()
        return self.model.objects.filter(
            tenant=tenant,
            approved=True,
            disbursed=True
        ).order_by('-disbursement_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)

        context.update(loan_count_metrics(tenant,status='disbursed'))
        return context


"""
DETAIL VIEW OF DISBURSED LOAN 
-- FULL/PARTIAL REPAYMENT 
-- SCHEDULE RECALCULATION
"""
class DisbursedLoanDetailView(DetailView):
    model = LoanApplication
    template_name = "disbursed_loan_details.html"
    context_object_name = 'loan'

    def get_object(self, queryset=None):
        tenant = getattr(self.request, 'tenant', None)
        loan_id = self.kwargs.get('pk')

        return self.model.objects.filter(
            tenant=tenant,
            id=loan_id,
            approved=True,
            disbursed=True
        ).first()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loan = self.get_object()
        # Next payment date calculation
        now = timezone.now()
        next_payment = LoanAmortizationSchedule.objects.filter(
            loan=loan,
            is_paid=False,
            installment_date__gte=now.date()
        ).order_by('installment_date').first()

        next_payment_date = next_payment.installment_date if next_payment else None

        # calculate loan metrics
        repayments = loan.loan_repayments.all().aggregate(
            total_principal=Sum('principal_paid'),
            total_interest=Sum('interest_paid')
        )
        total_interest = repayments['total_interest'] or Decimal('0.00')
        total_principal = repayments['total_principal'] or Decimal('0.00')

        total_repayments = Decimal(total_interest + total_principal)

        total_loan_amount = loan.amortization_schedule.all().aggregate(total=Sum('total_installment_amount'))['total'] or Decimal('0.00')

        context['next_payment_date'] = next_payment_date
        context['total_repayments'] = total_repayments
        context['outstanding_balance'] = (total_loan_amount - total_repayments).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        context['percentage_paid'] = Decimal((total_repayments / total_loan_amount * 100)).quantize(Decimal("0.01"), ROUND_HALF_UP) if total_loan_amount > 0 else Decimal('0.00')

        if loan:
            context['amortization_schedule'] = loan.amortization_schedule.all()
        else:
            context['amortization_schedule'] = []

        return context



"""
LOAN PAYMENT VIEW
--FULL/PARTIAL REPAYMENT
"""
class AdminLoanPaymentView(View):
    model = LoanApplication

    def post(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        loan_id = self.request.POST.get('loan_id')
        payment_amount_str = self.request.POST.get('payment_amount')
        payment_type = self.request.POST.get('payment_type')  # 'full' or 'partial'
        user = self.request.user
        print(f"USER: {user}")

        payment_amount = Decimal(payment_amount_str)
        total_amount_payable = Decimal('0.00')

        if not tenant or not user:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid request.'
            })
        if not loan_id or not payment_amount_str or not payment_type:
            return JsonResponse({
                'status': 'error',
                'message': 'Loan ID, Payment Type and Payment Amount are required.'
            })

        loan = self.model.objects.filter(
            tenant=tenant,
            id=loan_id,
        ).first()

        if not loan:
            return JsonResponse({
                'status': 'error',
                'message': 'Loan not found.'
            })

        # TODO continue from here next time -- handle admin loan repayment options
        print(f"Form Data {self.request.POST}")

        if payment_type == 'full':
            total_principal_paid = loan.loan_repayments.aggregate(
                total=Sum('principal_paid')
            )['total'] or Decimal('0.00')

            total_outstanding_principal = loan.amount_requested - total_principal_paid

            last_payment = loan.amortization_schedule.filter(
                is_paid=True
            ).order_by('-installment_date').first()

            if last_payment:
                days = (timezone.now().date() - last_payment.installment_date).days
                daily_rate = loan.interest_rate / Decimal('36500')
                total_accrued_interest = total_outstanding_principal * daily_rate * days
            else:
                total_accrued_interest = Decimal('0.00')

            total_amount_payable = total_outstanding_principal + total_accrued_interest

            if payment_amount < total_amount_payable:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Payment amount cannot be less than the total outstanding balance.'
                })

            # Record the full repayment
            LoanRepayment.objects.create(
                tenant=tenant,
                user=user,
                loan=loan,
                date_paid=timezone.now(),
                principal_paid=total_outstanding_principal,
                interest_paid=total_accrued_interest,
                is_full_payment=True,
                payment_type='full'
            )

            try:
                loan.handle_full_repayment()
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Error updating loan status: {e}'
                })

            return JsonResponse({
                'status': 'success',
                'message': 'Loan has been fully repaid and marked as PAID.'
            })


        if payment_type == 'partial':
            try:
                payment_amount = Decimal(payment_amount_str)
            except ValueError:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid payment amount.'
                })

            if payment_amount <= 0:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Payment amount must be greater than zero.'
                })

            #TODO: Handle partial repayment logic

            return JsonResponse({
                'status': 'success',
                'message': 'Partial repayment processing is not implemented yet.'
            })

        if payment_type == 'installment':
            amount = loan.monthly_installments
            #TODO: Handle installment payment logic

            return JsonResponse({
                'status': 'success',
                'message': 'Installment payment processing is not implemented yet.'
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid payment type. Must be "full", "partial", or "installment".'
            })


"""
REJECTED LOAN APPLICATIONS LIST VIEW
"""
class RejectedLoanApplications(ListView):
    model = LoanApplication
    template_name = 'rejected_applications.html'
    context_object_name = 'rejected_loans'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            return self.model.objects.filter(
                tenant=tenant,
                status='REJECTED',
            ).order_by('-application_date')
        return self.model.objects.none()
    

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)

        context.update(loan_count_metrics(tenant,status='rejected'))
        return context



"""
Function to return count metrics of loan applications
"""
def loan_count_metrics(tenant,status):
    model = LoanApplication

    queryset = model.objects.filter(
        tenant=tenant
    )
    context = {}

    if queryset:
        pending_applications_count = queryset.filter(
            status = "PENDING",
            approved = False
        ).count()

        approved_applications_count = queryset.filter(
            status = "APPROVED",
            approved = True
        ).count()

        disbursed_applications_count = queryset.filter(
            status = "DISBURSED",
            approved = True,
            disbursed = True
        ).count()

        rejected_applications_count = queryset.filter(
            status = "REJECTED",
            approved = False,
            disbursed = False
        ).count()

        context = {
        'pending_count':pending_applications_count,
        'approved_count':approved_applications_count,
        'disbursed_count':disbursed_applications_count,
        'rejected_count':rejected_applications_count,
        'active_tab':status
        }
    
    return context


"""
VIEW To fetch a specific loan details and return a JSON object
"""
class FetchLoanDetails(View):
    model = LoanApplication
    
    def get(self,request,*args,**kwargs):
        tenant = getattr(request,'tenant',None)
        loan_id = kwargs.get('loan_id')

        if not tenant:
            return JsonResponse({
                'status':'error',
                'message':'Invalid Request.'
            })
        
        if not loan_id:
            return JsonResponse({
                'status':'error',
                'message':'Loan ID missing.'
            })
        
        # Fetch Loan
        loan = self.model.objects.filter(
            tenant=tenant,
            id=loan_id,
        ).first()

        if not loan:
            return JsonResponse({
                'status':'error',
                'message':'Loan not found.'
            })
        
        return JsonResponse({
            'status':'success',
            'data':{
                'user':{
                    'id':loan.user.staff_id,
                    'username':loan.user.user.username,
                    'staff_id':loan.user.staff_id,
                    'position':loan.user.job_title,
                    'employment_date':loan.user.employment_date,
                    'contact':loan.user.tel_number,
                    'email':loan.user.user.email,
                    'department':loan.user.department
                },
                'loan':{
                    'id':loan.id,
                    'amount_requested':loan.amount_requested,
                    'tenure_months':loan.tenure_months,
                    'application_date':loan.application_date,
                    'approval_date':loan.approval_date,
                    'approved_by':loan.approved_by.__str__(),
                    'interest_rate':loan.interest_rate,
                    'monthly_installment':loan.monthly_installments,
                    'total_repayment':Decimal(0), #At this point there is no repayment
                    'purpose':loan.purpose,
                #     Rejection details
                    'rejected_date':loan.rejected_date,
                    'rejected_by':loan.rejected_by.__str__() if loan.rejected_by else None,
                }
            }
        })


class MemberLoanDetailView(ListView):
    model = LoanAmortizationSchedule
    template_name = 'member_loan_details.html'
    context_object_name = 'loan_amortization_schedule'
    paginate_by = 12

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        member = getattr(self.request.user, 'member', None)
        loan_id = self.kwargs.get('loan_id')

        if tenant and member and loan_id:
            print("Fetching Loan Amortization Schedule for Loan ID:", loan_id)
            return self.model.objects.filter(
                tenant=tenant,
                user=member,
                loan__id=loan_id
            ).order_by('installment_number')

        return self.model.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        member = getattr(self.request.user, 'member', None)
        loan_id = self.kwargs.get('loan_id')

        print(f"Amortizations: {self.get_queryset()}")

        if tenant and member and loan_id:
            loan = LoanApplication.objects.filter(
                tenant=tenant,
                user=member,
                id=loan_id
            ).first()

            if loan:
                context['loan'] = loan

        return context