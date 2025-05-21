from django.forms import model_to_dict
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.http import JsonResponse
from django.views.generic import ListView,CreateView,View,TemplateView,DetailView,UpdateView,DeleteView
from .models import LoanApplication,LoanRepayment,LoanType
from .forms import LoanForm,LoanTypeForm
from django.utils.decorators import method_decorator
from Member.decorators import tenant_login_required,tenant_required
from Admin.decorators import role_required
from decimal import Decimal,ROUND_HALF_UP
from django.utils import timezone


# Create your views here.

class LoanApplicationView(TemplateView):
    template_name = 'loan_application.html'

class LoanTypeView(ListView):
    model = LoanType
    template_name = 'loan_types.html'
    context_object_name = 'loan_types'
    paginate_by = 10



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


"""
CLASS TO CALCULATE AND DISPLAY EMI TO MEMBER
"""
class LoanDetails:
    def total_interest_flat(self, amount, tenure):
        p = Decimal(amount)
        r = Decimal('6.5')  # This must be made dynamic for each tenant
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
        annual_rate = Decimal('6.5')  # Make this tenant-specific later
        r = (annual_rate / Decimal('1200'))  # Monthly rate as decimal
        T = Decimal(tenure)

        if r == 0:
            emi = p / T  # Simple division if zero interest
        else:
            numerator = p * r * (1 + r) ** T
            denominator = ((1 + r) ** T) - 1
            emi = numerator / denominator

        return emi.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)



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


# Page for member to view and track loan detailsfrom decimal 
class MemberLoanPage(TemplateView):
    template_name = 'member_loan_page.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        tenant = getattr(self.request, 'tenant', None)
        member = getattr(self.request.user, 'member', None)

        loan = LoanApplication.objects.prefetch_related('loan_repayments').filter(
            tenant=tenant,
            user=member
        ).first() if tenant and member else None

        loan_repayments = loan.loan_repayments.all() if loan else []

        percentage_paid = self.calculate_percentage_paid(loan, loan_repayments) if loan else Decimal(0)

        amount_paid = sum(i.amount_paid for i in loan_repayments) if loan_repayments else Decimal(0.0)

        context.update({
            'loan': loan,
            'repayments': loan_repayments,
            'percentage_paid': percentage_paid,
            'amount_paid':amount_paid,
            'remaining_amount': loan.amount_requested - amount_paid,
            'count_of_repayments':loan_repayments.count(),
            'remaining_payments':loan.tenure_months - loan_repayments.count()
        })
        return context
    
    def calculate_percentage_paid(self, loan, payments):
        loan_amount = loan.amount_requested
        if loan_amount == 0:
            return Decimal(0)

        amount_paid = sum(i.amount_paid for i in payments) if payments else Decimal(0)

        percent = (amount_paid / loan_amount) * 100
        return percent.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    


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
                disbursed=False
            ).order_by(
                '-approval_date'
            )

        return self.model.objects.none()
    
    """
    HANDLE DISBURSEMENT OPERATION
    """
    # TODO: HANDLE DISBURSEMENT LOGIC
    def post(self,*args,**kwargs):
        return



    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant',None)
        
        context.update(loan_count_metrics(tenant,status='approved'))
        return context
    

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
        loan_id = kwargs.get('approved_loan_id')

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
            approved=True,
            disbursed=False,
            status='APPROVED'
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
                    'purpose':loan.purpose
                }
            }
        })
