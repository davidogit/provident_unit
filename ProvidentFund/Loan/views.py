import datetime

from django.db import IntegrityError, transaction
from django.db.models import Sum, DecimalField
from django.forms import model_to_dict
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.http import JsonResponse
from django.views.generic import ListView,CreateView,View,TemplateView,DetailView,UpdateView,DeleteView
from openpyxl.styles.builtins import total
from pyexpat.errors import messages

from Member.tasks import send_single_mail
from .models import LoanApplication, LoanRepayment, LoanType, LoanAmortizationSchedule, build_amortization_schedule,LoanTopUp
from .forms import LoanForm, LoanTypeForm, LoanTopUpRequestForm
from django.utils.decorators import method_decorator
from Member.decorators import tenant_login_required,tenant_required
from Admin.decorators import role_required
from decimal import Decimal,ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.utils import timezone


# Create your views here.

class LoanApplicationView(TemplateView):
    """
    Represents a view for handling loan-application-related functionality.

    This class extends TemplateView to render the loan application page and fetch
    additional context data based on the current tenant and the loan type specified
    in the request. It facilitates the integration of loan-specific information by
    overriding the context data for the page.
    """
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
    """
    Represents a view for displaying LoanType objects in a listing format.

    LoanTypeView is a subclass of ListView that provides functionality
    to display and paginate a queryset of LoanType objects. This view is
    designed to consider tenant-specific filtering for LoanType objects
    and displays them sorted by creation date in descending order.

    Attributes:
        model (Type[LoanType]): Specifies the model associated with the view.
        template_name (str): Defines the template used to render the view.
        context_object_name (str): The name of the context variable
            used to pass the queryset to the template.
        paginate_by (int): Defines the number of records displayed per page.
    """
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
    """
    Class-based view for creating a LoanType object.

    This view handles the creation of LoanType instances. It validates the
    provided form, ensures that the tenant is associated correctly, and responds
    with a JSON object indicating success or failure. It extends the Django
    CreateView and customizes form validation and success URL behavior.

    Attributes:
        model: Specifies the model associated with this view (LoanType).
        form_class: Specifies the form class used to create a LoanType.

    Methods:
        form_valid: Called when the submitted form data is valid.
        form_invalid: Called when the submitted form data is invalid.
        get_success_url: Determines the URL to redirect upon successful creation.
    """
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
    """
    Handles updating of LoanType objects.

    This class-based view provides functionality for securely updating LoanType
    objects associated with a specific tenant. It ensures tenant-based filtering
    and validation while handling update operations for the LoanType model.

    Attributes:
        model: The LoanType model being updated.
        form_class: The form class used to validate and update LoanType objects.
    """
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
    """
    A view to handle the deletion of LoanType objects.

    This class-based view is used to delete instances of the LoanType model. It
    ensures that only loan types associated with the current tenant can be
    retrieved and deleted. Additionally, it strictly prevents the deletion of loan
    types that are referenced by existing loan applications.

    Attributes:
        model (LoanType): The model that this DeleteView operates on.

    Methods:
        get_queryset:
            Returns the queryset limited to LoanType objects for the current
            tenant, or none if the tenant is not set.
        post:
            Handles the POST request for deleting a LoanType. Prevents deletion
            if the LoanType is referenced by loan applications.
        get_success_url:
            Provides the URL to redirect to after successful deletion of a
            LoanType.
    """
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
    """
    Represents a detailed view for a LoanType instance.

    This class is used to handle HTTP GET requests for retrieving specific details
    of a LoanType based on its id and validating tenant access. It checks if the
    authenticated tenant matches the tenant associated with the requested LoanType
    object. If the tenants do not match, it denies access, otherwise, it provides
    the required data as a serialized JSON response.

    Attributes:
        model (LoanType): Specifies the model associated with the view.
    """
    model = LoanType

    def get(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)

        loan_type = self.get_object()

        if tenant and loan_type.tenant != tenant:
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
    """
    HandleLoanSubmission is a class-based Django view to handle loan application
    submissions via HTTP POST requests.

    This view processes loan applications by validating request data, checking for
    eligibility, and saving the loan application to the database. It also ensures
    that both the tenant and the user (member) submitting the application exist. If
    specified, the loan type will be validated to ensure it is associated with the
    current tenant. On successful validation and saving, it returns a success
    response; otherwise, it returns error messages detailing the issues with the
    submission.
    """
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

        # check if the member has a pending loan application
        pending_loan_application = LoanApplication.objects.filter(
            tenant=tenant,
            user=member,
            status='PENDING'
        )
        if pending_loan_application.exists():
            return JsonResponse({
                'status':'error',
                'message':'You already have a pending loan application. You cannot apply for another loan at this time.'
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
    """
    Represents the details and calculations for a specific loan.

    The LoanDetails class performs various computations related to a loan, including
    interest, processing fees, monthly EMIs, total payable amount, and disbursement
    amount. It supports both flat and reducing interest calculation methods, using
    parameters provided for the loan type and tenure.

    Attributes:
        principal (Decimal): The principal loan amount.
        tenure_months (Decimal): The tenure of the loan in months.
        tenure_years (Decimal): The tenure of the loan in years, divided by 12.
        loan_type: The type of the loan, containing interest rate, calculation type, and fee percentage.
        annual_rate (Decimal): The annual interest rate derived from the loan type.
        monthly_rate (Decimal): The monthly interest rate derived by dividing the annual rate by 1200.
        processing_fee_percent (Decimal): The processing fee percentage derived from the loan type.
        interest_calc_type (str): The interest calculation type, either 'FLAT' or 'REDUCING'.

    Methods:
        total_interest_flat():
            Computes the total interest based on the flat rate calculation method.

        loan_processing_fee():
            Computes the processing fee for the loan.

        total_payable_amount_flat():
            Computes the total payable amount for the loan under flat rate calculation.

        disbursement_amount():
            Computes the disbursement amount after subtracting the processing fee.

        calculate_monthly_emi():
            Computes the monthly EMI amount based on the interest calculation type.

        estimate_total_interest():
            Estimates the total interest payable based on the interest calculation type.
    """
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
    """
    Handles the calculation of loan details and provides the necessary response.

    This class is a Django view responsible for processing loan-related calculations
    based on the request sent by the client. It extracts data from the request,
    validates it, fetches the correct loan type, and performs detailed computations
    such as loan processing fees, total payable amount, monthly installment, and
    disbursement amount.

    Attributes:
        None
    """
    def get(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
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
                'formatted_total_interest': (total_repayment-amount)
            }
        })


"""
MEMBER VIEW TO TRACK LOANS
"""
# Page for member to view and track loan details
class MemberLoanPage(ListView):
    """
    Represents a view that displays a paginated list of loan applications specific to a member.

    This class extends the ListView to provide functionality for viewing loan applications
    associated with a particular member of a tenant. It customizes the queryset to retrieve only
    approved and disbursed loans for the currently authenticated member within a specific tenant.

    Attributes:
        model: The model class associated with this ListView, which is LoanApplication.
        paginate_by: An integer specifying the number of objects to display per page.
        template_name: A string specifying the path to the template used by the view.
        context_object_name: A string defining the name of the context object in the template.
    """
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
    """
    View for displaying a paginated list of loan types specific to a tenant.

    This view retrieves and displays loan types associated with the tenant
    making the request. The results are paginated, rendered using a specific
    template, and assigned a context name for template access.

    Attributes:
        model : The model class being used for the query, representing loan types.
        template_name : Template file to render the results.
        paginate_by : The number of items displayed per page.
        context_object_name : The name of the context variable in the template.
    """
    model = LoanType
    template_name = 'member_loan_type_page.html'
    paginate_by = 10
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
    """
    Fetches loan type details based on tenant and loan type ID provided in the
    request.

    This class-based view handles GET requests to retrieve loan type details
    for a specified tenant. The tenant is identified based on the request's
    attributes, and the loan type is retrieved using the loan type ID passed
    as a query parameter.

    Attributes:
        None

    Methods:
        get(*args, **kwargs):
            Handles GET requests for fetching loan type details.
    """
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
    """
    LoanApprovalView is a view for managing and approving loan applications.

    This class extends Django's ListView and provides functionality to list
    pending loan applications for a specific tenant, approve loan applications
    via a POST request, and display additional loan-related metrics in the
    context data.

    Attributes:
        model: The model associated with the view, LoanApplication.
        template_name: The template used to render the page.
        paginate_by: The number of records displayed per page in the view.
        context_object_name: The context variable name for the list of loan applications.

    Methods:
        get_queryset: Filters loan applications based on the current tenant,
                      application's approval status, and application status.
        post: Handles loan approval requests submitted via POST.
        get_context_data: Extends the context data to include metrics
                          related to pending loan applications.
    """
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
    """
    Class for displaying and managing the disbursement of approved loans.

    This class is a Django ListView that interacts with the LoanApplication model to display
    a list of approved loans ready to be disbursed. It provides functionalities to filter
    loans based on approval and tenant status, handle loan disbursement actions through POST
    requests, and enhance the context data with additional loan metrics.

    Attributes:
        model: The LoanApplication model class the view interacts with.
        template_name: The name of the template file used to render the view.
        context_object_name: The name of the context variable containing the list
            of approved loans for use in the template.
    """
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
    """
    Manages the display and retrieval of disbursed loans in a paginated view.

    This class provides functionality to query and display disbursed loans
    specific to a tenant user. It renders the loans in a template while
    calculating and injecting additional context metrics related to the
    disbursed loans.

    Attributes:
        model (LoanApplication): The model used to query disbursed loans.
        paginate_by (int): Number of loans to display per page in the view.
        template_name (str): Path to the template rendering the view.
        context_object_name (str): Name of the object used in the template context.
    """
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
    """
    View to display detailed information about a disbursed loan.

    This class is used to fetch and present detailed data for a disbursed loan
    application. It ensures that the loan is associated with the current tenant
    and is both approved and disbursed. The view provides contextual data
    related to the loan, including next payment details, total repayments,
    outstanding balance, payment percentage, and the amortization schedule.
    It serves as a part of the loan management system for tenants.

    Attributes:
        model: The model class that this view is based on, which is LoanApplication.
        template_name: The path to the template used to render the view.
        context_object_name: The name of the variable through which the object is
                             made available in the template.

    Methods:
        get_object:
            Retrieves the loan object if it's approved and disbursed and is
            associated with the currently logged-in tenant.

        get_context_data:
            Provides additional context data, including loan metrics such as
            next payment date, total repayments, outstanding balance,
            payment percentage, and amortization schedule.

    Returns:
        Rendered template containing the detailed loan information based on
        the context data.
    """
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

        total_repayments = Decimal(total_interest + total_principal).quantize(Decimal('0.00'))

        total_loan_amount = loan.amount_requested + loan.interest_amount


        context['next_payment_date'] = next_payment_date
        context['total_repayments'] = total_repayments
        context['outstanding_balance'] = (total_loan_amount - total_repayments).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        context['percentage_paid'] = Decimal(((total_repayments / total_loan_amount) * 100)).quantize(Decimal("0.01"), ROUND_HALF_UP) if total_loan_amount > 0 else Decimal('0.00')

        if loan:
            context['amortization_schedule'] = loan.amortization_schedule.all()
        else:
            context['amortization_schedule'] = []

        return context


"""
RETURNS THE ACTUAL REQUIRED PAYABLE AMOUNT FOR A LOAN AT A GIVEN DATE
"""
class ActualAmountPayable:
    """
    Represents the calculation of the actual amount payable for a given loan application.

    Provides functionality to determine the total amount still payable on a loan, including
    outstanding principal and accrued interest, based on the payment and loan details.
    """
    def __init__(self,loan:LoanApplication):
        self.loan = loan

    def get_actual_amount_payable(self):
        loan = self.loan
        total_principal_paid = loan.total_principal_paid

        total_outstanding_principal = loan.amount_requested - total_principal_paid

        last_payment = loan.amortization_schedule.filter(
            is_paid=True
        ).order_by('-installment_date').first()

        if last_payment:
            days = (timezone.now().date() - last_payment.installment_date).days
            daily_rate = loan.interest_rate / Decimal('36500')
            total_accrued_interest = (total_outstanding_principal * daily_rate * days).quantize(Decimal('0.01'),
                                                                                                rounding=ROUND_HALF_UP)
        else:
            total_accrued_interest = Decimal('0.00')

        total_amount_payable = (total_outstanding_principal + total_accrued_interest).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return total_amount_payable



"""
VIEW TO FETCH FULL AMOUNT PAYABLE FOR A LOAN
"""
class FetchFullAmountPayable(View):
    """
    FetchFullAmountPayable class is responsible for handling HTTP GET requests to calculate
    and return the full amount payable for a specific loan application.

    This class interacts with the LoanApplication model to retrieve a specific loan object
    based on the provided loan ID and tenant information. It also utilizes the ActualAmountPayable
    class to calculate the full amount payable for the retrieved loan. This functionality
    is intended to be used in scenarios where precise payment amounts are required to be
    calculated for a loan.

    Attributes
    ----------
    model : LoanApplication
        The ORM model class used to retrieve loan application instances.
    """
    model = LoanApplication
    def get(self,request,*args, **kwargs):
        tenant = getattr(self.request,'tenant',None)
        loanId = request.GET.get("loan_id")

        if not tenant or not loanId:
            return JsonResponse({
                'status':'error',
                'message':'Unable to calculate amount payable at this time.'
            })
        loan = self.model.objects.filter(
            tenant=tenant,
            id=loanId
        ).first()

        if not loan:
            return JsonResponse({
                'status':'error',
                'message':'Loan not found.'
            })

        amount_payable_calculator = ActualAmountPayable(loan)
        return JsonResponse({
            'status':'success',
            'data': {
                'amount_payable': amount_payable_calculator.get_actual_amount_payable()
            }
        })

"""
LOAN PAYMENT VIEW
--FULL/PARTIAL REPAYMENT
"""
class LoanPaymentHandler(View):
    """
    View to handle loan payments by an admin user.

    This view manages both full and partial loan repayments for a given loan application.
    It processes payment submissions, calculates interest and principal amounts based
    on the payment type, and updates the loan records accordingly. The view ensures
    validation checks are performed before processing payments and handles edge cases
    such as invalid payment amounts, non-existent loans, and insufficient payments.

    Attributes:
        model: The model class representing the loan application (LoanApplication).

    Methods:
        post(request, *args, **kwargs): Processes a POST request for loan repayment.
    """
    model = LoanApplication

    def post(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        loan_id = self.request.POST.get('loan_id')
        payment_amount_str = self.request.POST.get('payment_amount')
        payment_type = self.request.POST.get('payment_type')  # 'full' or 'partial'
        user = getattr(request, 'user', None)
        print(f"USER: {user}")

        try:
            payment_amount = Decimal(payment_amount_str)
        except ValueError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid payment amount.'
            })

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

        if payment_type == 'full':
            total_payable_amount_calculator = ActualAmountPayable(loan)
            # total_principal_paid = loan.total_principal_paid
            #
            # total_outstanding_principal = loan.amount_requested - total_principal_paid
            #
            # last_payment = loan.amortization_schedule.filter(
            #     is_paid=True
            # ).order_by('-installment_date').first()
            #
            # if last_payment:
            #     days = (timezone.now().date() - last_payment.installment_date).days
            #     daily_rate = loan.interest_rate / Decimal('36500')
            #     total_accrued_interest = (total_outstanding_principal * daily_rate * days).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            # else:
            #     total_accrued_interest = Decimal('0.00')

            # total_amount_payable = total_outstanding_principal + total_accrued_interest
            total_amount_payable = total_payable_amount_calculator.get_actual_amount_payable()

            if payment_amount < total_amount_payable:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Payment amount cannot be less than the total outstanding balance.'
                })


            try:
                with transaction.atomic():
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
                    # Mark all amortization installments as paid
                    # TODO: David: Add third party payment gateway integration here
                    # TODO: if payment is successful, then proceed to handle full repayment
                    loan.handle_full_repayment()
                    subject = "Loan Repayment Confirmation"
                    message = (f"Your loan with ID: {loan.id} has been fully repaid. "
                               "Loan has been marked as repaid. "
                               "All installments have been marked as paid. "
                               "Thank you.")
                    email = user.email
                    send_single_mail.delay(email,message,subject)
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
            partial_payment_amount = payment_amount

            if payment_amount <= 0:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Payment amount must be greater than zero.'
                })

            # 1. Total principal paid so far
            total_principal_paid = loan.total_principal_paid

            total_outstanding_principal = loan.amount_requested - total_principal_paid

            if partial_payment_amount >= total_outstanding_principal:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Payment amount is too high. Use full repayment instead.'
                })

            # 2. Find the last paid installment (if any)
            last_paid_schedule = loan.amortization_schedule.filter(
                is_paid=True
            ).order_by('-installment_date').first()

            # 3. Calculate interest accrued since the last paid installment (or disbursement)
            last_payment_date = last_paid_schedule.installment_date if last_paid_schedule else loan.disbursement_date
            today = timezone.now().date()
            days = (today - last_payment_date).days if last_payment_date else 0

            interest_accrued = Decimal('0.00')
            if days > 0:
                daily_rate = loan.interest_rate / Decimal('36500')
                interest_accrued = (total_outstanding_principal * daily_rate * days).quantize(Decimal('0.01'))

            # 4. Deduct interest from payment, rest goes to principal
            if partial_payment_amount <= interest_accrued:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Partial payment is too small to cover accrued interest.'
                })

            principal_paid = partial_payment_amount - interest_accrued
            new_outstanding_principal = total_outstanding_principal - principal_paid

            try:
                with transaction.atomic():
                    # Record repayment
                    LoanRepayment.objects.create(
                        tenant=tenant,
                        user=user,
                        loan=loan,
                        date_paid=timezone.now(),
                        principal_paid=principal_paid,
                        interest_paid=interest_accrued,
                        is_full_payment=False,
                        payment_type='partial'
                    )

                    # TODO: David: Add third party payment gateway integration here
                    # TODO: if payment is successful, then proceed to handle full repayment
                    subject = "Partial Loan Repayment Confirmation"
                    message = (f"Your partial payment of: {payment_amount} for loan with ID: {loan.id} has been received. "
                               "The outstanding principal has been updated. ")
                    email = user.email
                    send_single_mail.delay(email,message,subject)

                    # Rebuild amortization schedule from today using a new principal
                    build_amortization_schedule(
                        loan=loan,
                        principal=new_outstanding_principal,
                        start_date=timezone.now().date()
                    )

            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Error processing partial repayment: {str(e)}'
                })

            return JsonResponse({
                'status': 'success',
                'message': f'Partial payment of {partial_payment_amount} recorded. Interest: {interest_accrued}, Principal: {principal_paid}'
            })

        return JsonResponse({
            'status': 'error',
            'message': 'Invalid payment type. Must be "full", "partial".'
        })


"""
REJECTED LOAN APPLICATIONS LIST VIEW
"""
class RejectedLoanApplications(ListView):
    """
    View for displaying rejected loan applications.

    The RejectedLoanApplications class is a subclass of ListView that is responsible
    for displaying a list of loan applications marked as rejected. It filters the
    loan applications based on the current tenant and the rejection status. The
    view is rendered using a specified template, and the context includes additional
    metrics about rejected loans for the current tenant.
    """
    model = LoanApplication
    template_name = 'rejected_applications.html'
    context_object_name = 'rejected_loans'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            return self.model.objects.filter(
                tenant=tenant,
                status='REJECTED',
                rejected=True
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
    """
    Generates a dictionary containing the counts of loan applications based on their
    statuses for a given tenant and returns contextual information about these counts
    including the active tab status.

    Parameters:
        tenant: The object representing the tenant for whom the loan application data
            is being queried.
        status: str
            Indicates the currently active status tab (e.g., "PENDING", "APPROVED",
            "DISBURSED", "REJECTED").

    Returns:
        dict
            A dictionary containing the count of loan applications categorized by their
            statuses ('pending_count', 'approved_count', 'disbursed_count',
            'rejected_count') along with the status of the currently 'active_tab'.
    """
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
            approved = True,
            disbursed = True
        ).count()

        rejected_applications_count = queryset.filter(
            status = "REJECTED",
            rejected = True
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
    """
    FetchLoanDetails class is responsible for handling the retrieval of loan application details.

    This class provides functionality to fetch information about a loan application for a given tenant
    and loan ID using a GET request. It validates the request for required parameters and returns loan
    and related user details in the form of a JSON response. If the tenant or loan ID is invalid or missing,
    or if the loan is not found, an appropriate error response is returned.

    Attributes:
        model: The model class associated with the retrieval of loan applications.
    """
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
                    'note':loan.note
                }
            }
        })


class MemberLoanDetailView(DetailView):
    """
    A view to display the loan amortization schedule for a member.

    This class-based view extends ListView to present detailed information
    about a specific loan's amortization schedule, tailored for a member. It
    retrieves and paginates amortization details and provides relevant context
    data for rendering in a template.

    Attributes
    ----------
    model : Model
        The model used for retrieving loan amortization schedules.
    template_name : str
        The name of the template for rendering the view.
    context_object_name : str
        The name of the context variable for the queryset.
    paginate_by : int
        The number of items to display per page.

    Methods
    -------
    get_queryset()
        Retrieves the queryset for loan amortization schedules, filtering
        based on tenant, member, and loan ID if available.
    get_context_data(**kwargs)
        Provides additional context data for the template, including loan
        information for the given tenant, member, and loan ID.
    """
    model = LoanApplication
    template_name = 'member_loan_details.html'
    context_object_name = 'loan'

    def get_object(self, queryset=None):
        tenant = getattr(self.request, 'tenant', None)
        member = getattr(self.request.user, 'member', None)
        loan_id = self.kwargs.get('pk')

        if tenant and member and loan_id:
            return self.model.objects.filter(
                tenant=tenant,
                user=member,
                id=loan_id,
                approved=True
            ).first()

        return self.model.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loan = self.get_object()

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

        total_repayments = Decimal(total_interest + total_principal).quantize(Decimal('0.00'))

        total_loan_amount = loan.amount_requested + loan.interest_amount

        context['next_payment_date'] = next_payment_date
        context['total_repayments'] = total_repayments
        context['outstanding_balance'] = (total_loan_amount - total_repayments).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        context['percentage_paid'] = Decimal(((total_repayments / total_loan_amount) * 100)).quantize(Decimal("0.01"), ROUND_HALF_UP) if total_loan_amount > 0 else Decimal('0.00')

        if loan:
            context['amortization_schedule'] = loan.amortization_schedule.all()
        else:
            context['amortization_schedule'] = []

        return context


class RejectLoanApplication(View):
    """
    Handles the rejection of loan applications.

    This class is a view that manages the logic for rejecting pending loan applications.
    It processes incoming POST requests, validates required data, ensures the loan
    application exists and is in a pending state, and calls the `reject_loan` method
    to change the status of the loan application to "Rejected".

    Attributes:
        None
    """
    def post(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        loan_id = self.request.POST.get('loan_id')
        user = getattr(request,'user', None)
        note = self.request.POST.get('notes')

        if not tenant or not loan_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid request. Missing tenant or loan ID.'
            })

        loan = LoanApplication.objects.filter(
            tenant=tenant,
            id=loan_id
        ).first()

        if not loan:
            return JsonResponse({
                'status': 'error',
                'message': 'Loan application not found.'
            })

        if loan.status != 'PENDING':
            return JsonResponse({
                'status': 'error',
                'message': 'Only pending applications can be rejected.'
            })

        try:
            loan.reject_loan(user, note=note)
            return JsonResponse({
                'status': 'success',
                'message': 'Loan application rejected successfully.'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Error rejecting loan application: {e}'
            })


class LoanTopUpRequestView(CreateView):
    """
    Handles requests for loan top-ups by extending the CreateView class.

    LoanTopUpRequestView is a Django-based view that processes loan top-up requests made
    by users. It ensures that the request meets all necessary criteria, validates the
    associated loan and user information, and creates a loan top-up record. This view
    handles both valid and invalid form submissions, returning appropriate JSON responses.

    Attributes:
        model: The model associated with the top-up request. This should be LoanTopUp.
        form_class: The form class used to validate and process requests. This should be
             a LoanTopUpRequestForm.

    Methods:
        form_valid: Processes a loan top-up request when the submitted form is valid.
        form_invalid: Handles form validation errors by returning a JSON response with
            details about the error.

    Parameters:
        model: Class variable specifying the model (LoanTopUp) to use for storing top-up
            request data.
        form_class: Class variable that determines the form class (LoanTopUpRequestForm)
            that validates the input data.
    """
    model = LoanTopUp
    form_class = LoanTopUpRequestForm

    def form_valid(self, form):
        tenant = getattr(self.request, 'tenant', None)
        member = getattr(self.request.user, 'member', None)

        if not tenant or not member:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid request.'
            })

        loan_id = self.request.POST.get('loan_id')
        if not loan_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Loan ID is required for top-up.'
            })

        loan = LoanApplication.objects.filter(
            tenant=tenant,
            id=loan_id,
            user=member
        ).first()

        if not loan:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid request. Missing application.'
            })

        if not loan.approved or not loan.disbursed:
            return JsonResponse({
                'status': 'error',
                'message': 'Loan must be approved before requesting a top-up.'
            })

        if loan.is_loan_fully_paid:
            return JsonResponse({
                'status':'error',
                'message':'This loan is closed for top up.'
            })

        if self.model.objects.filter(loan=loan, user=member, status='PENDING').exists():
            return JsonResponse({
                'status': 'error',
                'message': 'You already have a pending top-up request for this loan.'
            })

        form.instance.tenant = tenant
        form.instance.user = member
        form.instance.loan = loan

        form.save(commit=True)

        return JsonResponse({
            'status': 'success',
            'message': 'Top-up request submitted successfully.'
        })

    def form_invalid(self, form):
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid form data.',
            'errors': form.errors
        }, status=400)



"""
LOAN TOPUP APPROVAL VIEW
"""
class LoanTopUpApprovalView(ListView):
    model = LoanTopUp
    template_name = 'approve_topup.html'
    paginate_by = 10
    context_object_name = 'topups'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return self.model.objects.none()

        return self.model.objects.filter(
            tenant=tenant,
            status='PENDING'
        ).order_by('-requested_at')


"""
APPROVED LOAN TOP-UP VIEW
"""
class LoanTopUpDisbursementView(ListView):
    model = LoanTopUp
    paginate_by = 10
    template_name = 'disburse_topup.html'
    context_object_name = 'topups'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return self.model.objects.none()

        return self.model.objects.filter(
            tenant=tenant,
            approved=True,
            status='APPROVED'
        ).order_by('-requested_at')


"""
DISBURSED LOAN TOP-UP VIEW
"""
class DisbursedLoanTopUps(ListView):
    model = LoanTopUp
    paginate_by = 10
    template_name = 'disbursed_topups.html'
    context_object_name = 'topups'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return self.model.objects.none()

        return self.model.objects.filter(
            tenant=tenant,
            disbursed=True,
            status='DISBURSED'
        ).order_by('-disbursement_date')



"""
REJECTED TOP-UP REQUESTS VIEW
"""
class RejectedTopUpRequests(ListView):
    model = LoanTopUp
    paginate_by = 10
    template_name = 'rejected_topups.html'
    context_object_name = 'topups'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return self.model.objects.none()

        return self.model.objects.filter(
            tenant=tenant,
            rejected=True,
            status='REJECTED'
        ).order_by('-requested_at')



"""
LOAN TOP-UP APPROVAL HANDLER
"""
class LoanTopUpApprovalHandler(View):
    model = LoanTopUp

    def get_object(self, topup_id):
        tenant = getattr(self.request, 'tenant', None)

        if not tenant or not topup_id:
            return self.model.objects.none()

        return self.model.objects.filter(
            tenant=tenant,
            id=topup_id,
            status='PENDING'
        ).first()

    def post(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        topup_id = self.request.POST.get('topup_id')
        user = getattr(request,'user', None)

        if not tenant or not topup_id or not user:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid request.'
            })

        topup = self.get_object(topup_id)

        if not topup:
            return JsonResponse({
                'status': 'error',
                'message': 'Top-up request not found.'
            })

        try:
            topup.approve_topup(user)
            return JsonResponse({
                'status': 'success',
                'message': 'Top-up request approved successfully.'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Error approving top-up request: {e}'
            })



"""
LOAN TOP-UP DISBURSEMENT HANDLER
"""
class LoanTopUpDisbursementHandler(View):
    model = LoanTopUp

    def get_object(self, topup_id):
        tenant = getattr(self.request, 'tenant', None)

        if not tenant or not topup_id:
            return self.model.objects.none()

        return self.model.objects.filter(
            tenant=tenant,
            id=topup_id,
            status='APPROVED'
        ).first()

    def post(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        topup_id = self.request.POST.get('topup_id')
        user = getattr(request,'user', None)

        if not tenant or not topup_id or not user:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid request.'
            })

        topup = self.get_object(topup_id)

        if not topup:
            return JsonResponse({
                'status': 'error',
                'message': 'Top-up request not found.'
            })

        try:
            topup.disburse_topup(user)
            return JsonResponse({
                'status': 'success',
                'message': 'Top-up request disbursed successfully.'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Error disbursing top-up request: {e}'
            })

"""
LOAN TOP-UP REJECTION HANDLER
"""
class LoanTopUpRejectionHandler(View):
    model = LoanTopUp

    def get_object(self, topup_id):
        tenant = getattr(self.request, 'tenant', None)

        if not tenant or not topup_id:
            return self.model.objects.none()

        return self.model.objects.filter(
            tenant=tenant,
            id=topup_id,
            status='PENDING'
        ).first()

    def post(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        topup_id = self.request.POST.get('topup_id')
        user = getattr(request,'user', None)
        note = self.request.POST.get('notes')

        if not tenant or not topup_id or not user:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid request.'
            })

        topup = self.get_object(topup_id)

        if not topup:
            return JsonResponse({
                'status': 'error',
                'message': 'Top-up request not found.'
            })

        try:
            topup.reject_topup(user, note=note)
            return JsonResponse({
                'status': 'success',
                'message': 'Top-up request rejected successfully.'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Error rejecting top-up request: {e}'
            })


"""
VIEW TO RETURN LOAN AND LOAN TOP-UP DETAILS AS JSON
"""
class FetchLoanAndTopUpDetails(View):
    model = LoanTopUp

    def get_object(self, loan_id):
        tenant = getattr(self.request, 'tenant', None)

        if not tenant or not loan_id:
            return self.model.objects.none()

        return self.model.objects.filter(
            tenant=tenant,
            id=loan_id
        ).first()


    def get(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        top_up_id = kwargs.get('pk')

        if not tenant or not top_up_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid request.'
            })

        top_up = self.get_object(top_up_id)
        if not top_up:
            return JsonResponse({
                'status': 'error',
                'message': 'Top-up request not found.'
            })

        top_up_details = {
            'id': top_up.id,
            'topup_amount': top_up.topup_amount,
            'application_date': top_up.requested_at,
            'tenure_months': top_up.new_tenure_months,
            'purpose': top_up.topup_purpose
        }

        user = top_up.user
        user_details = {}
        if user:
            user_details = {
                'full_name': user.user.get_full_name(),
                'staff_id': user.staff_id,
                'department': user.department,
                'position': user.job_title,
                'employment_date': user.employment_date,
                'contact': user.tel_number
            }

        parent_loan = top_up.loan
        loan_details = {}
        if parent_loan:
            total_interest_and_principal = parent_loan.loan_repayments.all().aggregate(
                total_principal=Sum('principal_paid'),
                total_interest=Sum('interest_paid')
            )

            total_repayment = total_interest_and_principal['total_principal'] + total_interest_and_principal['total_interest'] if total_interest_and_principal['total_principal'] and total_interest_and_principal['total_interest'] else Decimal('0.00')

            outstanding_balance = (parent_loan.amount_requested + parent_loan.interest_amount) - total_repayment

            loan_details = {
                'amount_approved': parent_loan.amount_requested,
                'outstanding_amount': outstanding_balance,
                'payments_made': total_repayment,
                'payment_status': 'PAID' if parent_loan.is_loan_fully_paid else 'UNPAID'
            }


        return JsonResponse({
            'status': 'success',
            'data': {
                'topup':top_up_details,
                'user': user_details,
                'original_loan': loan_details
            }
        })