from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from django.db.models import Sum,Prefetch
from django.http import HttpRequest
from django.views.generic import TemplateView, ListView,DetailView,UpdateView,CreateView,DeleteView,View
import pandas as pd
from Fund.models import InvestmentDetail,DelayedInterest,BankInterestRate,ScheduledPaymentDates,Suppliers,Requisition,RequisitionItem,PaymentInvoice,PurchaseOrder,ReceivedItems
from Member.models import Member,WithdrawalRequest,SchemeApproval,Transaction,WithdrawalBatch
from MultiScheme.models import Tenant,SchemeSettings,TenantEventNotification
from contributions.models import StaffAPI, Contribution, Membership
from django.urls import reverse
from django.utils.decorators import method_decorator
from Admin.decorators import role_required
from .forms import InvestmentUpdateForm,InvestmentApprovalForm,InvestmentCreationForm
from Fund.tasks import actual_member_interest,rollover_inv_creation,send_excel_sheet_to_bank_for_payment,calculate_staff_contribution
from Member.tasks import gen_send_email
from django.core.exceptions import ValidationError
import logging
from django.utils import timezone
from datetime import datetime, timedelta
from django.utils.dateparse import parse_date
from urllib.parse import urlencode
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.core.exceptions import ObjectDoesNotExist
from Chart_of_Accounts.models import BankAccount, ChartOfAccounts, AccountMapping, AccountingService
from Fund.generate_invoice import generate_short_alpha_numeric_id,generate_purchase_invoice_number
from Admin.models import User
import openpyxl
from django.db import transaction
from Member.decorators import tenant_required,tenant_login_required
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from MultiScheme.models import InvestmentScheme
import csv
logger = logging.getLogger(__name__)

class LandingPage(TemplateView):
    template_name = 'dashboard/landing_page.html'

    def get(self,request,*args,**kwargs):
        # clear session data ie. login credentials
        request.session.flush()

        return super().get(request, *args, **kwargs)


class AccessDenied(TemplateView):
    template_name = 'dashboard/access_denied.html'

    def get(self, request, *args, **kwargs):
        # clear session data
        # request.session.flush()

        return super().get(request, *args, **kwargs)

# the name=dispatch means the decorators will work for POST,GET,PUT etc
@method_decorator(login_required, name='dispatch') 
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury Manager','Treasury Analyst','Treasury Supervisor','Scheme Manager','Scheme Analyst','Scheme Supervisor','Contributions Manager','Contributions Analyst','Contributions Supervisor','Finance Manager','Finance Analyst','Finance Supervisor']), name='dispatch')
class Invest(TemplateView):
    template_name = 'dashboard/finance.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = Tenant.objects.prefetch_related('staff_api').get(id=self.request.tenant.id)

        # Fetch schemes and related investments using prefetch
        schemes = InvestmentScheme.objects.filter(
            tenant=tenant,
            approved=True
        ).prefetch_related('member')

        investments = InvestmentDetail.objects.filter(
            investment_scheme__tenant=tenant,
            investment_scheme__approved=True,
            approved=True
        )

        estimated_amount = investments.filter(approval_status=False).aggregate(total=Sum('interest_amount'))['total'] if investments else Decimal(0)
        actual_revenue = investments.filter(approval_status=True, _status='Expired').aggregate(total=Sum('interest_amount'))['total'] or Decimal(0)

        """
        Calculating Percentage increase to members,investments,Estimated and Actual revenue compared to previous months
        """
        now =timezone.now()
        this_month = now.month
        this_year = now.year

        # Handle case where current month is january (1)
        if this_month == 1:
            last_month = 12
            last_month_year = this_year-1
        else:
            last_month = this_month-1
            last_month_year = this_year

        staff_members = tenant.staff_api.all()
        # Members who joined current month v Previous month
        current_month_members = staff_members.filter(
            date_joined__month = this_month,
            date_joined__year = this_year
        )
        previous_month_members = staff_members.filter(
            date_joined__month = last_month,
            date_joined__year = last_month_year
        )

        # Count Staff Members
        current_month_members_count = current_month_members.count()
        previous_month_members_count = previous_month_members.count()
        
        # Filter investments for current month and previous month
        current_month_inv = investments.filter(
            created_date__month = this_month,
            created_date__year = this_year
        )
        previous_month_inv = investments.filter(
            created_date__month=last_month,
            created_date__year = last_month_year
        )

        # Count investments
        current_month_inv_count = current_month_inv.count()
        previous_month_inv_count = previous_month_inv.count()

        # Sum up estimated revenue for all investments both current and previous
        current_month_estimated_revenue = sum(inv.calculate_inv_interest() for inv in current_month_inv)
        previous_month_estimated_revenue = sum(inv.calculate_inv_interest() for inv in previous_month_inv)

        # Sum up actual revenue for all investments both current and previous
        current_month_actual_revenue = sum((inv.calculate_inv_interest()/inv.remaining_days) for inv in current_month_inv)
        previous_month_actual_revenue = sum((inv.calculate_inv_interest()/inv.remaining_days) for inv in previous_month_inv)

        # Percentage difference calculator
        def calculate_percentage_diff(current,previous):
            if previous == 0:
                return 'N/A' 
            percentage_change = ((current-previous)/previous) * 100
            direction = 'up' if (current-previous) > 0 else 'down'
            return {
                'percentage':percentage_change,
                'direction':direction
            }

        # calculate percentage increase
        staff_growth = calculate_percentage_diff(current_month_members_count,previous_month_members_count)
        investment_growth = calculate_percentage_diff(current_month_inv_count,previous_month_inv_count)
        estimated_revenue_growth = calculate_percentage_diff(current_month_estimated_revenue,previous_month_estimated_revenue)
        actual_revenue_growth = calculate_percentage_diff(current_month_actual_revenue,previous_month_actual_revenue)

        # Gender Enrollment in Each Scheme
        gender_counts_by_scheme = {}
        for scheme in schemes:
            gender_counts = (
                scheme.member.values('gender')
                .annotate(count=Count('gender'))
            )
            gender_counts_by_scheme[scheme.name] = {
                'Male': next((item['count'] for item in gender_counts if item['gender'] == 'Male'), 0),
                'Female': next((item['count'] for item in gender_counts if item['gender'] == 'Female'), 0),
                'Other': next((item['count'] for item in gender_counts if item['gender'] == 'Other'), 0),
            }

        context.update({
            'total_interest':estimated_amount,
            'actual_revenue':actual_revenue,
            'active_inv':investments.count(),
            'active_members':staff_members.count(),
            'interest_rates':BankInterestRate.objects.all(),
            'investment_scheme':schemes,
            'gender_counts_by_scheme':gender_counts_by_scheme,
            'investment_growth':investment_growth,
            'estimated_revenue_growth':estimated_revenue_growth,
            'actual_revenue_growth':actual_revenue_growth,
            'staff_growth':staff_growth
        })
        return context


# Creating List View for model
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury Manager','Treasury Supervisor','Treasury Analyst']), name='dispatch')
class InvestmentListView(ListView):
    context_object_name = 'investment_list'
    model = InvestmentDetail
    template_name = 'dashboard/investment_list.html'
    paginate_by = 10

    def get_queryset(self):
        tenant = self.request.tenant
        scheme_id = self.request.scheme_name

        return InvestmentDetail.objects.filter(
            investment_scheme__tenant=tenant,
            investment_scheme__id = scheme_id,
        ).order_by('-created_date')


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        filters = {}
        selector = self.request.GET.get('inv_selector',None)
        page = self.request.GET.get('page',1)

        if selector:
            filters['investment_type'] = selector

        if filters:
            filtered_query = queryset.filter(**filters)
        else:
            filtered_query = queryset

        investment_count = queryset.count()
        T_bills_count = queryset.filter(investment_type='Treasury Bill').count() if queryset else 0
        F_deposit_count = queryset.filter(investment_type='Fixed Deposit').count() if queryset else 0


        T_bills_percentage = (T_bills_count / investment_count) * 100 if investment_count > 0 else 0
        F_deposit_percentage = (F_deposit_count / investment_count) * 100 if investment_count > 0 else 0


        if filtered_query:
            paginator = Paginator(filtered_query, self.paginate_by)
            try:
                paginated_queryset = paginator.page(page)

            except PageNotAnInteger:
                paginated_queryset = paginator.page(1)
            except EmptyPage:
                paginated_queryset = paginator.page(paginator.num_pages)

            context.update(
                {
                    'investments':paginated_queryset,
                    'paginator':paginator,
                    'investment_count':investment_count,
                    'T_bills_count':T_bills_count,
                    'F_deposit_count':F_deposit_count,
                    "T_bills_percentage": round(T_bills_percentage, 0),
                    "F_deposit_percentage": round(F_deposit_percentage, 0),
                }
            )

        return context
    

# AJAX request for searching investments based on types
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury Manager','Treasury Supervisor','Treasury Analyst']), name='dispatch')
class AjaxInvestmentTypeView(View):
    model = InvestmentDetail
    paginate_by = 10

    def get_queryset(self):
        tenant = self.request.tenant
        scheme_id = self.request.scheme_name

        return self.model.objects.filter(
            investment_scheme__tenant=tenant,
            investment_scheme__id=scheme_id
        ).order_by('approved','created_date')

    def get(self, request, *args, **kwargs):
        inv_type = self.request.GET.get('type')
        page = self.request.GET.get('page', 1)  # Default to page 1
        expiry_status = self.request.GET.get('expiry_status','') #for matured investments to be recognized
        recognized_inv = self.request.GET.get('recognized_inv',None) # For recorgnized investments page
        queryset = self.get_queryset()

        if inv_type:
            queryset = queryset.filter(
                investment_type=inv_type
            )
        if expiry_status == 'Expired': #For requests made from Approve matured Invs page
            # We filter by approved,approval_status and _status
            queryset = queryset.filter(
                _status=expiry_status,
                approved=True,
                approval_status=False,
            )
        if recognized_inv == 'True':
            queryset = queryset.filter(
                approval_status=True,
                approved=True,
                _status='Expired'
            )

        total_pages = 0
        current_page = 0
        if queryset.exists():  # Avoid pagination on empty queryset
            paginator = Paginator(queryset, self.paginate_by)
            total_pages = paginator.num_pages 
            try:
                paginated_queryset = paginator.page(page)
                current_page = paginated_queryset.number
                # print(paginated_queryset)
            except PageNotAnInteger:
                paginated_queryset = paginator.page(1)
            except EmptyPage:
                paginated_queryset = paginator.page(paginator.num_pages)

            investments_data = [
                {
                    'id':inv.id,
                    'invoice_number':inv.invoice_number,
                    'account_name':inv.account_name,
                    'investment_type':inv.investment_type,
                    'type_of_tbill':inv.type_of_tbill,
                    'account_type':inv.account_type,
                    'account_number':inv.account_number,
                    'principal_amount':inv.principal_amount,
                    'interest_percentage':inv.interest_percentage,
                    'interest_amount':inv.interest_amount,
                    'closing_amount':inv.closing_amount,
                    'interest_start_date':inv.interest_start_date,
                    'interest_end_date':inv.interest_end_date,
                    'tenure':inv.tenure,
                    'remaining_days':inv.remaining_days,
                    'status':inv.status,
                    'created_date':inv.created_date,
                    'updated_date':inv.updated_date,
                    'approved':inv.approved
                }
                for inv in paginated_queryset
            ]
        else:
            investments_data = []

        return JsonResponse({
            'status': 'success',
            'investments': investments_data,
            'pagination':{
                'total_pages': total_pages,
                'current_page': current_page,
                'type':inv_type
            }
        })
    
#  `/${tenant_id}/fund/${scheme_name}/investments/filter/`
# Investment Detail View
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury Manager','Treasury Supervisor','Treasury Analyst']), name='dispatch')
class InvestmentDetailView(DetailView):
    model = InvestmentDetail
    template_name = 'dashboard/investment_details.html'
    context_object_name = 'investment_detail'

    # We override the get_queryset method to be able to filter the objects before its being accesed in this view
    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        scheme_id = getattr(self.request, 'scheme_name', None)

        # Filtering Queryset by Tenant
        if tenant:
            return InvestmentDetail.objects.filter(
                investment_scheme__tenant=tenant,
                investment_scheme__id = scheme_id
            )
        else:
            return None

    def post(self, request, *args, **kwargs):
        tenant = request.tenant
        scheme_id = request.scheme_name
        inv_id = request.POST.get('inv_id')
        termination_date_str = request.POST.get('termination_date')
        termination_interest_str = request.POST.get('termination_interest')
        termination_interest_str = request.POST.get('termination_interest', '').strip()

        # Validate interest input
        try:
            termination_interest = Decimal(termination_interest_str)
        except (InvalidOperation, TypeError, ValueError):
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid termination interest amount. Please enter a valid number.'
            }, status=400)

        scheme = InvestmentScheme.objects.filter(
                tenant=tenant,
                id = scheme_id,
                approved=True
            ).prefetch_related('account_mapping').first()

        if not scheme:
            return JsonResponse({
                'status':'error',
                'message':'Investment scheme not found'
            })
        

        mapping = scheme.account_mapping.filter(name='Redeem Investment').first()
        if not mapping:
            return JsonResponse({
                'status':'error',
                'message':'Mapping not found. Make sure a mapping is created for this event then try again.'
            })


        if not inv_id or not termination_date_str:
            return JsonResponse({'status': 'error', 'message': 'Missing required parameters.'})

        try:
            termination_date = datetime.strptime(termination_date_str, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse({'status': 'error', 'message': 'Invalid termination date format.'})

        # Get investment to terminate
        try:
            inv = InvestmentDetail.objects.get(
                id=inv_id,
                approved=True,
                investment_scheme__tenant=tenant,
                investment_scheme__id=scheme_id
            )
        except InvestmentDetail.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': "Couldn\'t find investment"})

        current_date = timezone.now().date()
        if current_date>inv.interest_end_date:
            return JsonResponse({
                'status':'error',
                'message':'This investment is matured hence can\'t be terminated.'
            })

        # Calculate interest up to the termination date
        days_to_termination = (termination_date - current_date).days
        if days_to_termination < 0 or termination_date > inv.interest_end_date:
            return JsonResponse({'status': 'error', 'message': 'Termination date cannot be in the past or after maturity date.'})
        
        with transaction.atomic():
            inv.interest_amount = termination_interest
            inv.status = 'Expired'
            inv.interest_end_date = termination_date
            inv.termination_status = True
            inv.save()

            # Perform debit and credit operations
            accounting_service = AccountingService(tenant=tenant,user=self.request.user,scheme=scheme)
            action_name = 'Redeem Investment'
            description = 'Redeemed Investment'
            try:
                accounting_service.create_entry(action_name,Decimal(termination_interest),description)
            except ValidationError as e:
                return JsonResponse({'status':'error','message':str(e)})

        return JsonResponse({'status': 'success', 'message': 'Investment terminated successfully.'})



# Adding an investment
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury Analyst']), name='dispatch')
class AddInvestment(CreateView):
    model=InvestmentDetail
    template_name = 'dashboard/investment_form.html'
    form_class = InvestmentCreationForm

    def dispatch(self, request, *args, **kwargs):
        self.tenant = getattr(request, 'tenant', None)
        self.scheme_id = getattr(request, 'scheme_name', None)

        if not self.tenant or not self.scheme_id:
            return JsonResponse({'status': 'error', 'message': 'Tenant or scheme not found.'}, status=400)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update({
            'account_type':InvestmentDetail.account,
            'inv_type':InvestmentDetail.inv_type
        })
        return context
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['type_of_tbill'].required = False 
        return form
    
    def form_invalid(self, form):
        return JsonResponse({
            'status':'error',
            'message':f'An error occurred:{form.errors}'
        })

    def form_valid(self, form):
        tenant = self.tenant
        scheme_name = self.scheme_id

        if not tenant or not scheme_name:
            return JsonResponse({
                'status':'error',
                'message':'Tenant or scheme not found.'
            })

        scheme = InvestmentScheme.objects.filter(
            id=scheme_name,
            tenant=tenant,
            approved=True
        ).prefetch_related('account_mapping').first()

        if not scheme:
            return JsonResponse({
                'status':'error',
                'message':'Investment scheme not found'
            })
        
        mapping = scheme.account_mapping.filter(name='Investment').first()
        if not mapping:
            return JsonResponse({
                'status':'error',
                'message':'Mapping not found. Make sure a mapping is created for this event then try again.'
            })
        
        # Fetch investment principal
        investment_amount = form.cleaned_data['principal_amount']


        if self.request.POST.get('type_of_tbill') == '':
            form.instance.type_of_tbill = 'Fixed Deposit'

        form.instance.investment_scheme = scheme

        with transaction.atomic():
            self.object = form.save()

            # perform debit anf credit operations
            accounting_service = AccountingService(tenant=tenant,user=self.request.user,scheme=scheme)
            action_name = 'Investment'
            description = 'Investment purchased'
            try:
                accounting_service.create_entry(action_name,Decimal(investment_amount),description)
            except ValidationError as e:
                return JsonResponse({
                    'status':'error',
                    'message':f'{str(e)}'
                })

        return JsonResponse({
            'status':'success',
            'message':'Investment created successfully.',
            'redirect_url':self.get_success_url()
        })
    

    def get_success_url(self):
        scheme = getattr(self.request, 'scheme_name', None)
        tenant =  getattr(self.request, 'tenant', None)
        return reverse('investment_list', kwargs={'scheme_name':scheme, 'tenant_id':tenant.id}) 



@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury Manager']), name='dispatch')
class ApproveNewInvestments(ListView):
    model =  InvestmentDetail
    template_name = 'dashboard/approve_new_investments.html'
    paginate_by = 10
    context_object_name = 'new_investment_list'

    def get_queryset(self):
        tenant = self.request.tenant
        scheme_id = self.request.scheme_name
        return InvestmentDetail.objects.filter(
            investment_scheme__tenant=tenant,
            investment_scheme__id=scheme_id,
            approved=False,
            approval_status=False
        ).order_by('-created_date')
    
    def post(self,*args,**kwargs):
        tenant = self.request.tenant
        inv_id = self.request.POST.get('inv_id')

        if not inv_id:
            return JsonResponse({
                'status':'error',
                'message':'Please provide an ID for the specified investment.'
            })
        
        inv = InvestmentDetail.objects.filter(
            investment_scheme__tenant=tenant,
            id=inv_id,
            approved=False
        ).first()

        if not inv:
            return JsonResponse({
                'status':'error',
                'message':'Investment not found.'
            })

        # Approve Inbvestment
        inv.approved = True
        inv.save()

        return JsonResponse({
            'status':'success',
            'message':'Investment approved successfully.'
        })

# Updating an Investement's details
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury Analyst']), name='dispatch')
class InvestmentUpdateView(UpdateView):
    model = InvestmentDetail
    form_class = InvestmentUpdateForm
    template_name = 'dashboard/investment_update_form.html'

    # We override the get_queryset method to be able to filter the objects before its being accesed in this view
    def get_object(self):
        tenant = self.request.tenant
        scheme_id = self.request.scheme_name
        # get inv pk
        pk = self.kwargs['pk']
        print(f'SCHEME ID: {scheme_id}')
        return InvestmentDetail.objects.filter(
            pk=pk,
            investment_scheme__tenant=tenant,
            investment_scheme__id = scheme_id
        ).first()

    
    def form_valid(self, form):
        super().form_valid(form)
        return JsonResponse({'status':'success', 'redirect_url':self.get_success_url()})
    
    # Form instance
    def get_context_data(self, **kwargs):
        context= super().get_context_data(**kwargs)
        inv = self.object
        
        # Pass invoice number separately since its not part of the form
        context['invoice_number'] = inv.invoice_number

        form = InvestmentUpdateForm(instance=inv)
        context['form'] = form

        return context
    
    def get_success_url(self):
        scheme_id = self.request.scheme_name
        tenant =  self.request.tenant
        return reverse('investment_list', kwargs={'scheme_name':scheme_id, 'tenant_id':tenant.id})





# Updating rollover interest percentage field only
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury Analyst']), name='dispatch')
class RolloverInvestment(TemplateView):
    template_name = 'dashboard/rollover_percentage.html'

    def post(self, request, *args, **kwargs):
        tenant = self.request.tenant
        tenant_id = request.tenant.id
        scheme_id = request.scheme_name
        # Collect all data in Post request 
        rollover_rate_str = request.POST.get('rate') 
        start_date_str = request.POST.get('start_date')
        maturity_date_str = request.POST.get('maturity_date')
        rollover_amount_str = self.request.POST.get('principal')
        rollover_type = request.POST.get('rollover_type') #Principal,Interest or full rollover
        rollover_rate = Decimal(rollover_rate_str)
        rollover_amount = Decimal(rollover_amount_str)
        start_date=datetime.strptime(start_date_str, "%Y-%m-%d")
        maturity_date = datetime.strptime(maturity_date_str, "%Y-%m-%d")
        account_number = request.POST.get('account_number')
        pk = kwargs['pk']

        # Make sure mappings exist before we proceed further
        scheme = InvestmentScheme.objects.filter(
            id=scheme_id,
            tenant=tenant,
            approved=True
        ).prefetch_related('account_mapping').first()

        if not scheme:
            return JsonResponse({
                'status':'error',
                'message':'Investment scheme not found'
            })
        
        mapping = scheme.account_mapping.filter(name='Roll Over').first()
        if not mapping:
            return JsonResponse({
                'status':'error',
                'message':'Mapping not found. Make sure a mapping is created for this event then try again.'
            })

        # Increment rollover count of original investment
        try:
            inv = get_object_or_404(
                InvestmentDetail,
                pk=pk,
                investment_scheme__tenant=request.tenant,
                investment_scheme__id=scheme_id,
                approved=True,
                approval_status=False,
                termination_status=False
            )
        except:
            return JsonResponse({'status':'error', 'message':'Investment object not found', 'redirect_url': self.get_success_url()})

        # Prevent cases where rollover principal is greater than the return of the previous investment interest+principal
        print(f'New amount: {rollover_amount}')
        if rollover_amount > (inv.interest_amount + inv.principal_amount):
            message = f'Roll over principal cannot be greater than {(inv.interest_amount + inv.principal_amount)}'
            return JsonResponse({'status':'error','message':message})

        counter = 0
        # Increment rollover count
        if inv.rollover_count == 0:
            counter +=1
        else:
            counter = inv.rollover_count + 1

        # adding R[] to investment before saving
        name_parts = ''
        if inv.rollover_count>=1:
            name_parts = inv.account_name.split()#split name on spaces

            # Remove the last item(Naming conversion)
            name_parts = name_parts[:-1] #removes the naming conversion
            name_parts=" ".join(name_parts)
        else:
            name_parts = inv.account_name            

        inv_name = f'{name_parts} R{counter}'
        inv_type = inv.investment_type
        rollover_principal = rollover_amount
        account_type = inv.account_type

        # Check if rollover is principal only or principal+interest
        debit_or_credit_amount = None
        if rollover_type == 'principal':
            debit_or_credit = False
        else:
            debit_or_credit = True
            debit_or_credit_amount = inv.interest_amount

        required_fields = [
            tenant_id,
            scheme_id,
            inv_name,
            inv_type,
            rollover_rate,
            rollover_principal,
            start_date,
            maturity_date,
            account_number,
            account_type,
        ]

        # Validate all fields
        if not all(required_fields):
            return JsonResponse({'status':'error', 'message':'Some fields are missing'})
        # Call task to handle investment creation
        try:
            # Debit and Credit operations to be done in tasks after succesful entry of DI object
            rollover_inv_creation.delay(
                tenant_id=tenant_id,
                scheme_id=scheme_id,
                inv_name=inv_name,
                inv_type=inv_type,
                rollover_rate=rollover_rate,
                rollover_principal=rollover_principal,
                start_date=start_date,
                maturity_date=maturity_date,
                account_number=account_number,
                account_type=account_type,
                counter=counter,
                compounding_frequency=inv.compounding_frequency,
                duration = inv.years,
                debit_or_credit =debit_or_credit , #determins if a debit or credit operation is needed
                debit_or_credit_amount = debit_or_credit_amount, #amount to be credited or debited based on full or partial rollover
            )
            inv.roll_over = True
            inv.save()
            return JsonResponse({'status':'success', 'redirect_url': self.get_success_url()})
        except ValidationError as e:
            return JsonResponse({'status':'error', 'message':str(e.message)})
        except Exception as e:
            return JsonResponse({'status':'error', 'message':str(e)})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get Tenant
        tenant = self.request.tenant
        # Get scheme name
        scheme_id = self.request.scheme_name
        # Get inv pk
        pk = self.kwargs['pk']

        # Fetch investment
        if tenant:
            inv = get_object_or_404(
                InvestmentDetail,
                pk=pk,
                approved=True,
                investment_scheme__tenant=tenant,
                investment_scheme__id=scheme_id
            ) 
        
        context['rollover']= inv
        return context
    
    def get_success_url(self):
        scheme_id = self.request.scheme_name
        tenant =  self.request.tenant
        return reverse('investment_list', kwargs={'scheme_name':scheme_id, 'tenant_id':tenant.id})


# Deleting an Investment from Database
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury Analyst']), name='dispatch')
class InvestmentDeleteView(TemplateView):
    # model = InvestmentDetail
    context_object_name = 'investment'
    template_name = 'dashboard/delete_investment.html'

    def get_object(self,request,pk):
        tenant = request.tenant
        scheme_id = request.scheme_name
        
        if tenant:
            return InvestmentDetail.objects.filter(
                pk=pk,
                approved=True,
                investment_scheme__tenant=tenant,
                investment_scheme__id=scheme_id
            ).first()
        return None

    def delete(self, request, *args, **kwargs):
        print('Started Deletion')
        pk = kwargs.get('pk')
        investment = self.get_object(request, pk)

        if not investment:
            return JsonResponse({
                'status': 'error',
                'message': 'Investment not found.'
            }, status=404)

        if investment.interest_start_date <= timezone.now().date():
            return JsonResponse({
                'status': 'error',
                'message': 'This investment has begun and cannot be deleted.'
            }, status=400)

        try:
            investment.delete()
            return JsonResponse({
                'status': 'success',
                'message': 'Investment deleted successfully.',
                'redirect_url': reverse('investment_list', kwargs={'scheme_name': request.scheme_name, 'tenant_id': request.tenant.id})
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'An error occurred while deleting the investment: {str(e)}.'
            }, status=500)


# Exited Members List
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Scheme Manager','Scheme Analyst']), name='dispatch')
class ExitedMembers(ListView):
    model = StaffAPI
    template_name ='dashboard/exited_members.html'
    paginate_by=20


    # We override the get_queryset method to be able to filter the Members before its being accesed in this view
    def get_queryset(self):  
        # Get Tenant
        tenant = self.request.tenant
        scheme_id = self.request.scheme_name

        # Filtering Queryset by Tenant
        if tenant:
            return StaffAPI.objects.filter(tenant=tenant, investment_scheme__id=scheme_id)
        else:
            return StaffAPI.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Filtering members based on their exit_flags
        queryset = self.get_queryset().filter(exited_flag = True)
        context['results'] = queryset

        context['exited_members'] = queryset.count()

        context['total_members'] = self.get_queryset().count()

        return context

  

# Memeber detailed View
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=[]), name='dispatch')
class MemberDetailView(DetailView):
    # model = Member
    model = StaffAPI
    template_name = 'dashboard/member_details.html'

    # We override the get_queryset method to be able to filter the Members before its being accesed in this view
    def get_queryset(self):
         
        # Get Tenant
        tenant = self.request.tenant
        scheme_id = self.request.scheme_name

        # Filtering Queryset by Tenant
        if tenant:
            return StaffAPI.objects.filter(tenant=tenant, investment_scheme__id=scheme_id)
        else:
            return StaffAPI.objects.none()


# Query For Investment View
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury Manager','Treasury Supervisor','Treasury Analyst']), name='dispatch')
class InvestmentQuery(ListView):
    template_name = 'dashboard/query.html'
    model = InvestmentDetail
    paginate_by = 10  # Set the number of results per page

    def get_queryset(self):
        # Get Tenant
        tenant = self.request.tenant
        # Get scheme id
        scheme_id = self.request.scheme_name

        # Filtering Queryset by Tenant
        if tenant:
            return InvestmentDetail.objects.filter(
                approved=True,
                investment_scheme__id=scheme_id,
                investment_scheme__tenant=tenant
            ).order_by('-created_date')
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset() or self.model.objects.none()

        # Get filter parameters
        sort = self.request.GET.get('sort')
        from_date_str = self.request.GET.get('from-date')
        to_date_str = self.request.GET.get('to-date')
        inv_type = self.request.GET.get('inv_type')
        status = self.request.GET.get('status')
        invoice_number = self.request.GET.get('invoice_number')
        type_of_tbill = self.request.GET.get('type_of_tbill')

        from_date = parse_date(from_date_str) if from_date_str else None
        to_date = parse_date(to_date_str) if to_date_str else None

        # check if filters are applied
        filters_applied = any([sort,from_date_str,to_date_str,inv_type,status,invoice_number,type_of_tbill])

        if not filters_applied:
            queryset = queryset.none()
        
        else:
            # Apply filters incrementally
            if inv_type:
                queryset = queryset.filter(investment_type=inv_type)

            if type_of_tbill:
                queryset = queryset.filter(type_of_tbill=type_of_tbill)
            
            if invoice_number:
                queryset = queryset.filter(invoice_number=invoice_number)

            if status:
                if status == 'matured':
                    queryset = queryset.filter(_status='Expired')
                elif status == 'active':
                    queryset = queryset.filter(_status='Active')
                elif status == 'Not started':
                    queryset = queryset.filter(_status='Not Start')

            if from_date and to_date:
                if sort == 'interest_start_date':
                    queryset = queryset.filter(interest_start_date__range=(from_date, to_date))
                elif sort == 'created_date':
                    queryset = queryset.filter(created_date__range=(from_date, to_date))

            # Apply sorting (default to 'interest_start_date' if no sort parameter is given)
            sort_field = sort or 'interest_start_date'
            queryset = queryset.order_by(sort_field)

        # Apply pagination
        paginator = Paginator(queryset, self.paginate_by)
        page = self.request.GET.get('page')

        try:
            paginated_queryset = paginator.page(page)
        except PageNotAnInteger:
            paginated_queryset = paginator.page(1)
        except EmptyPage:
            paginated_queryset = paginator.page(paginator.num_pages)

        # Generate query parameters for pagination links
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            query_params.pop('page')
        query_string = urlencode(query_params)

        # Add paginated results to context
        context['results'] = paginated_queryset
        context['paginator'] = paginator
        context['is_paginated'] = paginator.num_pages > 1
        context['query_string'] = query_string
        return context



# List view for delayed interest
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury Manager','Treasury Supervisor','Treasury Analyst']), name='dispatch')
class DelayedInterestListView(ListView):
    """
    View responsible for managing a paginated list of delayed interest records.

    This view handles the display and approval of delayed interests for
    a specific tenant and investment scheme. It ensures appropriate role-based
    access and provides functionalities for filtering, approving, and updating
    delayed interests along with handling associated debit/credit operations.

    Attributes:
        template_name (str): Path to the template used for rendering the view.
        model (Type[Model]): The model associated with the view.
        paginate_by (int): Number of items to display per page in pagination.
        context_object_name (str): Name of the context variable for the data passed
            to the template.

    Methods:
        get_queryset: Retrieves a filtered queryset of delayed interests based on
            tenant and scheme.
        post: Processes approval actions on delayed interests, performs debit/credit
            operations, and saves status updates.
        get_context_data: Fetches and calculates additional context variables for
            rendering in the template.
    """
    template_name = 'dashboard/delayed_interest_list.html'
    model = DelayedInterest
    paginate_by = 10
    context_object_name = 'delayed_interest'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        scheme_id = getattr(self.request, 'scheme_name', None)

        if tenant:
            return DelayedInterest.objects.filter(investment_scheme__tenant=tenant,investment_scheme__id = scheme_id).order_by('status','-created_date')
        else:
            return DelayedInterest.objects.none()
    
    # Post method to handle approval and debit/credit operations
    def post(self, *args, **kwargs):
        tenant = getattr(self.request, 'tenant', None)
        scheme_id = getattr(self.request, 'scheme_name', None)
        delayed_int_id = self.request.POST.get('d_int_id', None)

        # Validate required fields
        fields = [tenant, scheme_id, delayed_int_id]
        if not all(fields):
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required fields'
            })

        # Fetch investment scheme
        scheme = InvestmentScheme.objects.filter(
            id=scheme_id, tenant=tenant, approved=True
        ).prefetch_related('delayed_interest', 'account_mapping').first()

        if not scheme:
            return JsonResponse({
                'status': 'error',
                'message': 'Investment scheme not found.'
            })


        mapping = scheme.account_mapping.filter(name='Approved Delayed Interest').first()
        if not mapping:
            return JsonResponse({
                'status': 'error',
                'message': 'Mapping not found. Make sure a mapping is created for this event then try again.'
            })


        # Fetch the delayed-interest object
        delayed_interest_object = scheme.delayed_interest.filter(id=delayed_int_id).first()
        if not delayed_interest_object:
            return JsonResponse({
                'status': 'error',
                'message': 'Delayed interest object not found.'
            })

        with transaction.atomic():
            # Validate delayed interest amount
            delayed_interest_amount = delayed_interest_object.principal
            if delayed_interest_amount <= 0:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid delayed interest amount.'
                })

            # Update delayed interest status
            delayed_interest_object.approved = True
            delayed_interest_object.status = 'Paid'
            delayed_interest_object.approved_by = self.request.user
            delayed_interest_object.save()

            # Perform debit and credit operations
            accounting_service = AccountingService(tenant=tenant, user=self.request.user,scheme=scheme)
            action_name = 'Approved Delayed Interest'
            description = 'Approved Delayed Interest'

            try:
                accounting_service.create_entry(action_name,delayed_interest_amount,description)
            except ValidationError as e:
                return JsonResponse({'status': 'error', 'message': str(e.message)})

        return JsonResponse({
            'status': 'success',
            'message': 'Delayed interest approved successfully.'
        })


    
    def get_context_data(self, **kwargs):
        context=super().get_context_data(**kwargs)
        page_number = self.request.GET.get('page', 1)
        start_index = (int(page_number) - 1) * self.paginate_by + 1
        queryset = self.get_queryset()
        total_d_int = queryset.count()
        paid_d_interest = queryset.filter(status='Paid',approved=True).count()
        context['delayed_int_count'] = total_d_int
        context['total_paid']=paid_d_interest
        context['not_paid_d_interest'] = (total_d_int-paid_d_interest)
        context['total_amount'] = queryset.all().aggregate(total=Sum('principal'))['total'] or Decimal(0.0)
        context['start_index'] = start_index
        return context
    

# Search Delayed Interest View
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury Manager','Treasury Supervisor','Treasury Analyst']), name='dispatch')
class DelayedInterestSearchView(View):
    def get(self,request,*args,**kwargs):
        tenant = self.request.tenant
        search_term = self.request.GET.get('search_term','')
        scheme_id = self.kwargs['scheme_name']
        print(f'Scheme ID: {scheme_id}')
        if not search_term:
            return JsonResponse({
                'status':'error',
                'message':'Search term is required'
            })
        
        results = DelayedInterest.objects.filter(
            Q(remarks__icontains=search_term)|
            Q(invoice_number__icontains=search_term),
            investment_scheme__tenant=tenant,
            investment_scheme__id=scheme_id
        )
        print(f'Results: {results}')
        delayed_interest_list = [
            {
                'id':d.pk,
                'invoice_number':d.invoice_number,
                'principal':d.principal,
                'created_date':d.created_date,
                'remarks':d.remarks,
                'status':d.status,
                'rate':d.rate_d_int
            }
            for d in results
        ]

        return JsonResponse({
            'status':'success',
            'data':delayed_interest_list
        })


# Delayed Interest Query
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury Manager','Treasury Supervisor','Treasury Analyst']), name='dispatch')
class DelayedInterestQuery(ListView):
    model = DelayedInterest
    template_name = 'dashboard/delayed_interest_query.html'
    paginate_by = 20
    # We override the get_queryset method to be able to filter the objects before its being accesed in this view
    def get_queryset(self):
        # Get Tenant
        tenant = self.request.tenant

        # Get scheme name
        scheme_id = self.request.scheme_name

        # Filtering Queryset by Tenant
        if tenant:
            return DelayedInterest.objects.filter(investment_scheme__tenant=tenant,investment_scheme__id = scheme_id).order_by('-created_date')
        else:
            return DelayedInterest.objects.none()
        

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        # Get search parameters from the request
        invoice_number = self.request.GET.get('invoice_number','').strip()
        from_date, to_date = None, None
        print(invoice_number)
        # Safely parse dates
        try:
            from_date = datetime.strptime(self.request.GET.get('from-date'), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            pass
        try:
            to_date = datetime.strptime(self.request.GET.get('to-date'), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            pass

        # Apply filters if any search parameter is provided
        if invoice_number:
            queryset = queryset.filter(invoice_number=invoice_number)
        if from_date and to_date:
            queryset = queryset.filter(created_date__range=(from_date, to_date))
        elif from_date:
            queryset = queryset.filter(created_date__gte=from_date)
        elif to_date:
            queryset = queryset.filter(created_date__lte=to_date)
        # Set queryset to none if no filters were applied
        if not (invoice_number or from_date or to_date):
            queryset = queryset.none() 
 
        context['results'] = queryset

        return context

    


# Approval of investments
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury Supervisor']), name='dispatch')
class ApproveMaturedInvestment(ListView):
    model = InvestmentDetail
    paginate_by = 10
    template_name = 'dashboard/matured_investment_approval.html'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        scheme_id = getattr(self.request, 'scheme_name', None)

        if tenant and scheme_id:
            # Matured investments to be approved
            return InvestmentDetail.objects.filter(
                investment_scheme__tenant=tenant, investment_scheme__id=scheme_id,
                approval_status=False,
                approved=True,
                _status='Expired'
            )
        else:
            return InvestmentDetail.objects.none()
        
    def post(self, request, *args, **kwargs):
        form = InvestmentApprovalForm(request.POST)
        inv_id = request.POST.get('investment_id')
        tenant = request.tenant
        scheme_id = request.scheme_name
        tenant_id = tenant.id

        if not inv_id:
            return JsonResponse({'status': 'error', 'message': 'Investment ID is required.'})

        scheme = InvestmentScheme.objects.filter(
            tenant=tenant,id=scheme_id,approved=True
        ).prefetch_related('account_mapping').first()

        if not scheme:
            return JsonResponse({'status': 'error', 'message': 'Investment scheme not found.'})

        if form.is_valid():
            investment = self.get_queryset().filter(id=inv_id).first()
            closing_amount = form.cleaned_data.get('closing_amount')
            approval_status = form.cleaned_data.get('approval_status')

            # Validate that 'closing_amount' and 'approval_status' are provided
            if closing_amount is None or approval_status is None:
                return JsonResponse({'status': 'error', 'message': 'Closing amount and approval status are required.'})
            
            # Fetch related mapping obj
            if not scheme:
                return JsonResponse({
                    'status':'error',
                    'message':'Investment scheme not found.'
                })

            mapping = scheme.account_mapping.filter(name='Approved Revenue').first()
            if not mapping:
                return JsonResponse({
                    'status':'error',
                    'message':'Mapping not found. Make sure a mapping is created for this event then try again.'
                })

            # Check if closing amount == expected amount
            with transaction.atomic():
                if investment.interest_amount==closing_amount:
                    investment.approval_status = approval_status
                    investment.closing_amount = closing_amount
                    investment.save()

                    # perform debit and credit operation
                    accounting_service = AccountingService(tenant=tenant, user=request.user,scheme=scheme)
                    action_name = 'Investment Approval'
                    description = 'Investment Approval'

                    try:
                        accounting_service.create_entry(action_name,investment.interest_amount,description)
                    except ValidationError as e:
                        return JsonResponse({'status': 'error', 'message': str(e.message)})

                    # After saving changes now we calculate members' actual profit using tasks
                    actual_member_interest.delay(tenant_id,scheme_id,inv_id)

                    return JsonResponse({'status':'success','message':'Investment approved successfully and accounts updated.'})
                else:
                    # Gather the error message
                    error_message = 'Closing amount does not match with expected amount'
                    return JsonResponse({'status':'error', 'message':error_message})

        return JsonResponse({'status':'error','message':'Invalid form data.'})


    def get_context_data(self, **kwargs):
        context=super().get_context_data(**kwargs)

        context['approval_form']=InvestmentApprovalForm()
        return context


# Approved Investments list
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury Manager','Treasury Supervisor','Treasury Analyst']), name='dispatch')
class ApprovedInvestments(ListView):
    model = InvestmentDetail
    template_name = 'dashboard/approved_investments.html'
    paginate_by = 10

    def get_queryset(self):
        tenant = self.request.tenant
        scheme_id = self.request.scheme_name

        if tenant and scheme_id:
            return InvestmentDetail.objects.filter(
                investment_scheme__tenant=tenant,
                investment_scheme__id=scheme_id,
                approval_status=True,
                approved=True,
                _status='Expired'
            ).order_by('-created_date')
        else:
            return InvestmentDetail.objects.none()



# LIST OF SCHEME APPLICATION APPROVALS
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Scheme Supervisor']), name='dispatch')
class SchemeApplications(ListView):
    model = SchemeApproval
    template_name = 'dashboard/scheme_application_approval.html'
    context_object_name = 'schemeapproval_list'
    paginate_by = 20

    def get_queryset(self):
        tenant = self.request.tenant

        if tenant:
            try:
                # Filter where scheme hasnt been approved and tenant
                return SchemeApproval.objects.filter(tenant=tenant)
            except SchemeApproval.DoesNotExist:
                return SchemeApproval.objects.none()
        return super().get_queryset().none()
    
    
    # Using dispatch to be able to access the post method which is not directly in Listview
    def dispatch(self, request, *args, **kwargs):
        if request.method == 'POST':
            return self.handle_post(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)
    

    # Method to handle the posted data
    def handle_post(self,request, *args, **kwargs):
        tenant = request.tenant
        application_id = request.POST.get('application_id')
        approved_by_hr = request.POST.get('approved_by_hr')


        try:
            application = self.get_queryset().get(tenant=tenant, id=application_id)

            # Now we can approve using the approve method on the SchemeApproval Model
            application.approve()

            from contributions.models import Membership
            # Create MEMBERSHIP
            Membership.objects.create(
                tenant=application.tenant,
                staff=application.staff,
                scheme = application.scheme,
            )

            # Notify applicant upon scheme approval
            applicant_email = application.member.user.email
            try:
                # Email notification to user
                subject='Your Scheme Application Approved'
                message=f'Your application to enroll onto {application.scheme.name} has been approved successfully. Deductions will start at the end of the current month'
                recipient=applicant_email
                gen_send_email.delay(recipient,message,subject)

            except Exception:
                logger.info(f'couldnt send application approved message to {application.member.user.username}')
            return JsonResponse({'status':'success', 'approved_by_hr':approved_by_hr})
        except SchemeApproval.DoesNotExist:
            return JsonResponse({'status':'error'},status=400)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        total = queryset.count()
        pending = queryset.filter(approved_by_hr=False).count()
        context['total_applications'] = total
        context['pending_applications'] = pending
        context['approved'] = (total-pending)
        return context

@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=[]), name='dispatch')
class RecentActivities(ListView):
    model = InvestmentDetail
    template_name = 'dashboard/all_history.html'
    paginate_by = 20

    def get_queryset(self):
        tenant = self.request.tenant
        if tenant:
            return InvestmentDetail.objects.filter(investment_scheme__tenant=tenant).order_by('created_date')
        return InvestmentDetail.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        tenant = self.request.tenant
        if tenant:
            inv_list = self.get_queryset() #Using the 'object_list to maintain the pagination
            history_list = []

            for inv in inv_list:
                inv_history = inv.history.all().order_by('history_date')  # Ensure records are ordered

                # See detailed changes eg.. What fields were changed
                # Make comparison only if records are 2 or more
                if inv_history.count() > 1:
                    for i in range(1, inv_history.count()):
                        # latest record
                        new_record = inv_history[i]
                        # previous record
                        old_record = inv_history[i - 1]

                        # Find the changes in fields between the two records
                        delta = new_record.diff_against(old_record)
                        changes = []
                        for change in delta.changes:
                            changes.append({
                                'field': change.field,
                                'old_value': change.old,
                                'new_value': change.new
                            })

                        # Store the history and its changes together
                        history_list.append({
                            'instance': inv,
                            'history_instance': new_record,
                            'history_date': new_record.history_date,
                            'history_user': new_record.history_user,
                            'history_change': new_record.get_history_type_display(),
                            'field_changes': changes
                        })

            # context names and pagination
            # paginator = Paginator(history_list, self.paginate_by)
            # page = int(self.request.GET.get('page'))
            
            # history_page = paginator.get_page(page)
            
            # Add paginated history_list to the context
            context['investment_history'] = history_list
            # context['is_paginated'] = history_page.has_other_pages()
            # context['page_obj'] = history_page
            # context['paginator'] = paginator
        return context



# Contribution Approval
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Contributions Manager','Contributions Supervisor','Contributions Analyst']), name='dispatch')
class ApproveContributions(TemplateView):
    template_name = 'dashboard/approve_contributions.html'

    def post(self,request,*args,**kwargs):
        tenant = getattr(request, 'tenant', None)
        scheme_id = getattr(request, 'scheme_name', None)
        tenant_id = tenant.id
        month = request.POST.get('month')
        year = request.POST.get('year')
        message_1 = '' #holder for an extra message to user

        scheme = InvestmentScheme.objects.filter(
            id=scheme_id,
            tenant=tenant,
            approved=True
        ).prefetch_related('account_mapping').first()
        
        if not scheme:
            return JsonResponse({
                'status':'error',
                'message':'Investment scheme not found.'
            })

        mapping = scheme.account_mapping.filter(name='Approved Contribution').first()
        if not mapping:
            return JsonResponse({
                'status':'error',
                'message':'Mapping not found. Make sure a mapping is created for this event then try again.'
            })

        delayed_int_mapping = scheme.account_mapping.filter(name='Delayed Interest').first()
        if not delayed_int_mapping:
            return JsonResponse({
                'status':'error',
                'message':'Mapping for Delayed Interest not found. Make sure a mapping is created for this event then try again.'
            })
        
        if not month and year:
            return JsonResponse({
                'status':'error',
                'message':'Month and Year are required'
            })
        
        # collect settings related to the scheme
        settings = SchemeSettings.objects.filter(
            investment_scheme=scheme,
            investment_scheme__tenant=tenant
        ).first()

        if not settings:
            return JsonResponse({
                'status':'error',
                'message':'Ensure scheme settings is configured and try again'
            })
       
        # Collect investments within the provided month
        contributions = Contribution.objects.filter(
            investment_scheme__tenant=tenant,
            investment_scheme=scheme,
            month=month,
            year=year,
            approved_contribution=False)

        if not contributions:
            return JsonResponse({'status': 'error', 'message': 'No contributions found for the given month.'})
        
        # Aggregate total_contributions
        total_contribution = contributions.aggregate(
                total=Sum('total_contribution')
        )['total'] or Decimal(0.0)

        if total_contribution == Decimal(0.0):
            return JsonResponse({
                'status':'error',
                'message':'Total contributions is zero.'
            })
        
        # Approve contributions and perform debit and credit operations
        with transaction.atomic():
            # Fetch debit and credit accounts from mapping obj
            debit_account = mapping.debit_acc
            credit_account = mapping.credit_acc

            if not debit_account or not credit_account:
                return JsonResponse({
                    'status':'error',
                    'message':'Debit or Credit accounts not properly configured'
                })
            
            # update contributions
            contributions.update(approved_contribution=True)
            
            # perform debit anf credit operations
            accounting_service = AccountingService(tenant=tenant, user=request.user,scheme=scheme)
            action_name = 'Approved Contribution'
            description = 'Approved Contribution'

            try:
                accounting_service.create_entry(action_name,total_contribution,description)
            except ValidationError as e:
                return JsonResponse({'status': 'error', 'message': str(e.message)})

        # update staff contributions using a task
        calculate_staff_contribution.delay(
            scheme_id,
            tenant_id,
            month,
            year
        )

        contribution_day = settings.contribution_day
        grace_period = settings.grace_period_contribution
        rate = settings.delayed_interest_rate
        # Check for Delayed Interest on Contribution
        now = timezone.now()

        # First day of the month
        first_day_of_month = now.replace(day=1,month=int(month),year=int(year))

        # expected payment date
        due_date = first_day_of_month + timedelta(contribution_day)

        grace_period_end = due_date + timedelta(grace_period)

        if now > grace_period_end:
            # Calculate delayed interest principal = accrued interest on contributions until approval date after grace period

            # monthly contribution total
            month_contribution = Contribution.objects.filter(
                investment_scheme__tenant=tenant,
                investment_scheme__id=scheme_id,
                month=month,
                year=year,
                approved_contribution=True
            ).aggregate(
                total=Sum('total_contribution')
            )['total'] or Decimal(0.0)

            # Calculate amount due after the grace period
            duration = (now - grace_period_end).days

            # convert percentage --> decimal
            daily_delayed_rate = Decimal(rate/100)

            # Using compound interest to calculate the delayed Interest on contribution
            t = Decimal(duration/365) #convert duration from days to years
            n = 365
            p = Decimal(month_contribution)
            r = daily_delayed_rate
            c = Decimal(p*(1+(r/n))**(n*t)).quantize(Decimal("0.01"), ROUND_HALF_UP) #compound interest asuming t=1 year
            delayed_principal = c-p

            # create a delayed interest object
            DelayedInterest.objects.create(
                investment_scheme=scheme,
                remarks = f'Delayed Interest for {month} /{year}',
                rate_d_int = rate,
                period_of_interest_calculation =settings.period_of_delayed_calculation,
                principal = delayed_principal,
            )

            with transaction.atomic():
                # perform debit anf credit operations
                accounting_service = AccountingService(tenant=tenant, user=request.user,scheme=scheme)
                action_name = 'Delayed Interest'
                description = 'Delayed Interest Created'

                try:
                    accounting_service.create_entry(action_name,delayed_principal,description)
                except ValidationError as e:
                    return JsonResponse({'status': 'error', 'message': str(e.message)})

            message_1 = (
                f'This payment is overdue hence a delayed interest entry is created for '
                f'the month of {month}/{year}'
            )
        message = f'Successfully approved investments for {month}/{year}, and Accounts updated successfully  NB:{message_1}'
        return JsonResponse({'status':'success', 'message':message})


@method_decorator(tenant_login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Contributions Manager','Contributions Supervisor','Contributions Analyst']), name='dispatch')
class FetchContributions(TemplateView):
    def get(self, request: HttpRequest, *args, **kwargs):
        tenant = request.tenant
        scheme_id = request.scheme_name
        month = request.GET.get('month')
        year = request.GET.get('year')

        if not month or not year:
            return JsonResponse({'status': 'error', 'message': 'Month and year are required.'})
        try:
            # Fetch data
            # from contributions.models import Contribution
            queryset = Contribution.objects.filter(investment_scheme__id=scheme_id,investment_scheme__tenant=tenant,month=month,year=year)


            # If no contributions are found, return an appropriate response
            if not queryset.exists():
                return JsonResponse({'status': 'error', 'message': 'No contributions found for the given criteria.'})


            total_number = queryset.count()
            total_amount = queryset.aggregate(total_amount=Sum('total_contribution'))['total_amount'] or 0
            contribution_date = queryset.first().contribution_date
            contribution_status = queryset.first().approved_contribution

            # object response
            return JsonResponse({
                'number_of_contributions':total_number,
                'total_amount':total_amount,
                'date_of_contribution':contribution_date,
                'contribution_status':'Validated' if contribution_status else 'Pending',
                'status':'success'
            })
        except Exception as e:
            return JsonResponse({'status':'error', 'message':str(e)})

from Member.models import ExitApproval
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Scheme Supervisor']), name='dispatch')
class ApproveExitedMembers(TemplateView):
    # model = ExitApproval
    template_name = 'dashboard/exiting_members.html'
    # context_object_name = 'exiting_members'

    def post(self,request,*args,**kwargs):
        tenant = getattr(request, 'tenant', None)
        scheme_id = getattr(request, 'scheme_name', None)

        application_id = request.POST.get('application_id')
        approved = request.POST.get('approved')
        member_id = request.POST.get('member_id')
        staff_id = request.POST.get('staff_id')

        if not tenant and not scheme_id:
            return JsonResponse({'status':'error', 'message':'Bad Request'})

        member = get_object_or_404(Member,id=member_id)

        if tenant and application_id and approved:
            application = ExitApproval.objects.get(tenant=tenant,member=member,id=application_id)

            if application:
                try:
                    application.approved = True
                    application.approval_date = timezone.now()
                    application.save()

                    # Remove scheme from memeber list of schemes
                    staff = get_object_or_404(StaffAPI,tenant=tenant,Id=staff_id)

                    # Scheme to remove from member list of schemes
                    scheme_to_remove = get_object_or_404(
                        InvestmentScheme,
                        tenant=tenant,
                        id=scheme_id,
                        approved=True
                    )

                    # Remove schemes and save staff instance
                    staff.investment_scheme.remove(scheme_to_remove)
                    staff.save()

                    # Delete Previous application to scheme
                    try:
                        SchemeApproval.objects.get(tenant=tenant,scheme=scheme_to_remove,member=member).delete()
                    except:
                        return JsonResponse({'status':'error','message':'Application approved but Member cannot apply to this scheme in the future. Contact Management to resolve this issue.'})


                    # Notify member of successful exit
                except Exception as e:
                    return JsonResponse({'status':'error','message':'Application cannot be approved at the moment'})

                return JsonResponse({'status':'success', 'message':'Exit Application approved successfully'})
            else:
                return JsonResponse({'status':'error', 'message':'Application cannot be approved at the moment'})
        else:
            return JsonResponse({'status':'error', 'message':'Something went wrong, can not approve application at this time. Try again later'})

    def get_context_data(self, **kwargs):
        tenant = self.request.tenant
        context = super().get_context_data(**kwargs)
        context['exiting_members']= ExitApproval.objects.filter(tenant=tenant,approved=False)

        return context



class MissingSchemeCodeError(Exception):
    def __init__(self, missing_codes):
        self.message = f"Invalid scheme code(s): {', '.join(map(str, missing_codes))}"
        super().__init__(self.message)

@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Super User']), name='dispatch')
class MassMemberUpload(CreateView):
    model = StaffAPI
    fields = '__all__'
    template_name = 'dashboard/mass_enroll.html'

    def post(self, request, *args, **kwargs):
        if not request.FILES.get("excel_sheet"):
            return JsonResponse({'status': 'error', 'message': 'No file uploaded'})

        tenant = request.tenant
        excel_file = request.FILES["excel_sheet"]

        try:
            wb = openpyxl.load_workbook(excel_file, read_only=True, data_only=True)
            sheet = wb.active
        except Exception:
            return JsonResponse({'status': 'error', 'message': 'Unsupported file format'})

        created_count = 0
        updated_count = 0
        error_message = ''

        for row in sheet.iter_rows(min_row=2, values_only=True):
            if all(cell in (None, '') for cell in row):
                continue

            try:
                # Unpack 13 expected fields
                (
                    staff_number, first_name, last_name, scheme_name, fund_type,
                    contributions, actual_amount, subscription_date,
                    contribution_date, employee_amount, employer_amount,
                    retro_employee_amount, retro_employer_amount
                ) = row

                # Clean and convert dates
                subscription_date = subscription_date.date() if isinstance(subscription_date, datetime) else subscription_date
                contribution_date = contribution_date.date() if isinstance(contribution_date, datetime) else contribution_date

                # Convert amounts to decimals safely
                employee_amount = Decimal(employee_amount or 0)
                employer_amount = Decimal(employer_amount or 0)
                retro_employee_amount = Decimal(retro_employee_amount or 0)
                retro_employer_amount = Decimal(retro_employer_amount or 0)
                contributions = Decimal(contributions or 0)
                actual_amount = Decimal(actual_amount or 0)

                # Get or create staff
                staff, created = StaffAPI.objects.get_or_create(
                    tenant=tenant,
                    staff_number=staff_number,
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'fund_type': fund_type,
                        'subscription_date': subscription_date,
                        'contributions': contributions,
                        'actual_amount': actual_amount,
                    }
                )

                if not created:
                    updated_count += 1
                else:
                    created_count += 1

                # Link staff to scheme
                scheme = InvestmentScheme.objects.filter(name=scheme_name, tenant=tenant, approved=True).first()
                if not scheme:
                    error_message += f"Scheme not found: {scheme_name} for {staff_number}\n"
                    continue

                staff.investment_scheme.add(scheme)

                # Ensure membership exists
                Membership.objects.get_or_create(
                    tenant=tenant,
                    staff=staff,
                    scheme=scheme
                )

                # Create contribution record
                Contribution.objects.create(
                    investment_scheme=scheme,
                    member=staff,
                    contribution_date=contribution_date,
                    employee_amount=employee_amount,
                    employer_amount=employer_amount,
                    retro_employee_amount=retro_employee_amount,
                    retro_employer_amount=retro_employer_amount,
                    approved_contribution=True
                )

            except Exception as e:
                error_message += f"Error processing row {row}: {str(e)}\n"

        return JsonResponse({
            'status': 'success',
            'message': f'{created_count} member(s) created, {updated_count} updated.\nIssues:\n{error_message or "None"}'
        })

                
                # Check if staff already exists






# Create an Exception to be called when theres Missing IDs in member scheme ID list when uploading members
# class MissingSchemeIdError(Exception):
#     def __init__(self, missing_ids, message = 'Scheme with ID(s) ', *args):
#         self.missing_ids = missing_ids
#         self.message = f'{message}: {missing_ids}'
#         super().__init__(self.message)

# # MASS MEMBER UPLOAD
# @method_decorator(login_required, name='dispatch')
# @method_decorator(tenant_required, name='dispatch')
# @method_decorator(role_required(role=['Super User']), name='dispatch')
# class MassMemberUpload(CreateView ):
#     model= StaffAPI
#     fields =('__all__')
#     template_name = 'dashboard/mass_enroll.html'
    
#     def post(self, request, *args, **kwargs):
#         print('There was a post request to this view')
#         if request.FILES["excel_sheet"]:
#             tenant = request.tenant
#             excel_file = request.FILES["excel_sheet"]
#             # Try creating users
#             try:
#                 # Secutity check on file before processing
#                 try:
#                     wb = openpyxl.load_workbook(excel_file,read_only=True,data_only=True) #load file
#                     sheet = wb.active #read file
#                 except Exception:
#                     return JsonResponse({
#                         'status':'error',
#                         'message':'Unsuported File Format'
#                     })

#                 # scheme list
#                 member_scheme_ids = []
#                 # Members list
#                 all_members=[]
#                 # Accumulate error messages when assigning schemes
#                 error_message = ''

#                 for row in sheet.iter_rows(min_row=2,values_only=True):
#                     if all(cell in (None,'') for cell in row):
#                         continue #skip empty rows
#                     else:   
#                         try:
#                             # Get data from rows --> fields
#                             staff_number,first_name,last_name,scheme_id,contributions,actual_amount,subscription_date = row
#                             # Convert scheme ids to a list
#                             if isinstance(scheme_id,str):
#                                 scheme_id = scheme_id.split(',')
#                             elif isinstance(scheme_id,int):
#                                 scheme_id = [scheme_id]
#                             else:
#                                 return JsonResponse({
#                                     'status':'error',
#                                     'message':f'Invalid data type for scheme id for staff: {staff_number}'
#                                 })

#                             # create member instance
#                             member_instance = StaffAPI(
#                                 tenant=tenant,
#                                 staff_number=staff_number,
#                                 first_name= first_name,
#                                 last_name=last_name,
#                                 contributions=contributions,
#                                 actual_amount=actual_amount,
#                                 subscription_date=subscription_date
#                             )
#                             # Add member to list
#                             all_members.append(member_instance)
#                             # Get all scheme id's
#                             member_scheme_ids.append(scheme_id if scheme_id else []) #split scheme ids

#                         except Exception as e:
#                             return JsonResponse({
#                                 'status':'error',
#                                 'message':f'Error processing rows{row}: {str(e)}\n'
#                             })
#                 try:
#                     with transaction.atomic():
#                         # Save members without schemes
#                         created_members = StaffAPI.objects.bulk_create(all_members)

#                         # Refresh created_members after bulk create to assign pks to them
#                         created_members = StaffAPI.objects.filter(staff_number__in=[member.staff_number for member in all_members])

#                         # Now set schemes on all members
#                         for member,scheme_id in zip(created_members,member_scheme_ids):
#                             # Fetch related schemes
#                             try:
#                                 # Fetch related schemes
#                                 schemes = InvestmentScheme.objects.filter(
#                                     tenant=tenant, id__in=scheme_id,
#                                     approved=True
#                                 )

#                                 # Assign scheme to member
#                                 member.investment_scheme.add(*schemes) #use list upacking to pass objects one by one

#                                 # Catch missing schemes in scheme_id provided
#                                 if len(scheme_id) != len(schemes):
#                                     missing_ids = set(scheme_id)- set(schemes.values_list('id', flat=True))
#                                     print(missing_ids)
#                                     raise MissingSchemeIdError(missing_ids) #raise custom error
#                             except MissingSchemeIdError as e:
#                                 error_message += f'{e.message} not found for: {member.last_name} {member.first_name} || \n'
#                                 continue
#                             except Exception as e:
#                                 print(e)
#                                 error_message += f'{e} for: {member.last_name} {member.first_name} || \n'
#                 except Exception as e:
#                     return JsonResponse({
#                         'status':'error',
#                         'message':f'An error occured: {e}'
#                     })
                
#                 return JsonResponse({
#                     'status':'success',
#                     'message': f'Members uploaded successfully\n {"" if error_message=="Invalid scheme ID for: " else error_message}'
#                 })
            
#             except Exception as e:
#                 return JsonResponse({
#                     'status':'error',
#                     'message':f'An error occured: {str(e)}'
#                 })
            
#         else:
#             return JsonResponse({
#                 'status':'error',
#                 'message':'Couldnt Find File'
#             })


# General Payout View
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Scheme Supervisor']), name='dispatch')
class GeneralPayoutView(TemplateView):
    template_name = 'dashboard/general_payout.html'

    def post(self,*args,**kwargs):
        tenant = self.request.tenant
        scheme_id = self.request.POST.get('scheme_id')
        staff_ids = self.request.POST.getlist('staff_ids[]')#List of selected staffs to be processed
        withdrawal_request_ids = self.request.POST.getlist('ref_ids[]')
        
        if not tenant or not scheme_id:
            return JsonResponse({
                'status':'error',
                'message':'Invalid Tenant or Scheme ID'
            }, status = 400) #Bad Request
        
        if not staff_ids or not withdrawal_request_ids:
            return JsonResponse({
                'status':'error',
                'message':'Select a staff and payout type'
            })

        if len(staff_ids) != len(withdrawal_request_ids):
            return JsonResponse({
                'status':'error',
                'message':'Mismatch in staff and withdrawal reference IDs'
            })
        
        try:
            scheme = InvestmentScheme.objects.get(
                id = scheme_id,
                tenant = tenant,
                approved=True
            )
        except Exception as e:
            logger.info(f'Scheme not found: {str(e)}')
            return JsonResponse({
                'status':'error',
                'message':'Scheme not found.'
            })
        
        try:
            email = TenantEventNotification.objects.filter(
                tenant=tenant,
                event = 'withdrawal_second_approval'
            ).values_list('staff__email', flat=True)

            if not email:
                return JsonResponse({
                    'status':'error',
                    'message':'No action mapping found for this event: second level approval of withdrawal request.'
                })
        except TenantEventNotification.DoesNotExist:
            logger.error('Could not find TenantEventNotification model.')
            return JsonResponse({
                'status':'error',
                'message':'An error occured. Please try again.'
            })
        except Exception as e:
            logger.error(f'An error occured: {str(e)}')
            return JsonResponse({
                'status':'error',
                'message':f'An error occured.'
            })
        
        # Fetch related account mapping for processing payouts
        all_withdrawals = []
        # Fetch selected scheme to be processed
        try: 
            # Get withdrawal requests
            for staff_id,withdrawal_id in zip(staff_ids,withdrawal_request_ids):
                withdrawal = WithdrawalRequest.objects.filter(tenant=tenant,id=withdrawal_id,staff__Id=staff_id).first()
                all_withdrawals.append(withdrawal)

                if not withdrawal:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Invalid withdrawal request for staff ID {staff_id}.'
                    })

            # Create withdrawal batch
            try:
                batch = WithdrawalBatch.objects.create(
                    tenant = tenant,
                    scheme = scheme,
                    # bank = bank,
                    # mode_of_payment = mode_of_payment
                )
            except Exception as e:
                return JsonResponse({
                    'status':'error',
                    'message':'Failed to create batch withdrawal object.'
                })
            # Bulk create Transactions
            try:
                with transaction.atomic():
                    # Assign withdrawals to a parent batch
                    for withdrawal in all_withdrawals:
                        withdrawal.parent_batch = batch
                    WithdrawalRequest.objects.bulk_update(
                        all_withdrawals,
                        fields=['parent_batch']
                    )
                    # approve batch and children requests
                    batch.approve_batch(approval_level=1)
            except Exception as e:
                logger.info(f'An error occured {e}')
                return JsonResponse({
                    'status':'error',
                    'message':'An error occured'
                })
            

            # Send email with link for approval
            from django.conf import settings
            base_url = settings.SITE_URL
            reverse_url = reverse('email_withdrawal_approval', kwargs={
                'tenant_id':tenant.id,
                'batch_id':batch.id,
                'scheme_id':scheme_id
            })
            url = f'{base_url}{reverse_url}'
            subject = f'Batch Withdrawal Approval'
            message = f'Please click here to approve batch withdrawal {batch}: {url}.'
            
            print('START 5')
            print(list(email))
            try:
                gen_send_email.delay(
                    recepient=list(email),
                    subject=subject,
                    message=message
                )
            except Exception as e:
                logger.error(f'An error occured: {str(e)}')
                return JsonResponse({
                    'status':'error',
                    'message':f'An error occured: {str(e)}'
                })
            print('START 6')
            # Perform Payment Processing task for selected members
            # Create Payout invoice
            # create transaction for each member
            
            # Perform Debit and Credit operations
            # consider bank and cheque operations

            return JsonResponse({
                'status':'success',
                'message':'Payout invoice created successfully.'
            })
            
        except Exception as e:
            logger.info(f'Error during general payout processing: {e}')
            return JsonResponse({
                'status':'error',
                'message':f'An internal server error occurred. Please try again later.'
            },status = 500) #Internat Server Error
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        
        context['schemes'] = InvestmentScheme.objects.filter(
            tenant=tenant,
            approved=True
        )

        return context

# Fetch Scheme Members for Payout
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Scheme Supervisor']), name='dispatch')
class FetchWithdrawalRequests(View):
    def get(self, request, *args, **kwargs):
        tenant = request.tenant
        scheme_id = self.request.GET.get('scheme_id')

        if not tenant or not scheme_id:
            return JsonResponse({
                'status':'error',
                'message':'Invalid Tenant or Scheme ID'
            }, status = 400) #Bad Request
        
        try:
            scheme = InvestmentScheme.objects.filter(
                id=scheme_id,
                tenant=tenant,
                approved=True
            ).first()

            if not scheme:
                return JsonResponse({
                    'status':'error',
                    'message':'Scheme not found'
                }, status = 404) #Not Found
            
            # Filter only unapproved requests
            filtered_withdrawals = WithdrawalRequest.objects.filter(
                tenant=tenant,
                scheme=scheme,
                first_approval=False,
                second_approval=False,
                third_approval=False,
                fourth_approval=False
            )

            # Fetch member withdrawal applications
            staffs = StaffAPI.objects.filter(
                tenant=tenant,
                investment_scheme__id=scheme_id,
                exited_flag=False
            ).prefetch_related(Prefetch('withdrawal_request', queryset=filtered_withdrawals))
            withdrawal_list = []
            for staff in staffs:
                withdrawals = staff.withdrawal_request.all()
                for w in withdrawals:
                    withdrawal_list.append(
                        {
                            'staff_id':w.staff.Id,
                            'staff_number':w.staff.staff_number,
                            'id':w.id,
                            'first_name':w.staff.first_name,
                            'last_name':w.staff.last_name,
                            'amount':w.amount,
                            'request_date':w.request_date,
                            'last_withdrawal_date':w.staff.last_withdrawal_date
                        }
                    )
            return JsonResponse({
                'status':'success',
                'message':'Success',
                'members': withdrawal_list
            })
            
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message':f'An error occured: {str(e)}'
            }, status = 500) #Internal Server Error

        
# SECOND STAGE OF APPROVAL FOR WITHDRAWAL REQUEST THROUGH EMAIL
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Supervisor']), name='dispatch')
class SecondPhaseOfWithdrawalApproval(ListView):
    template_name = 'dashboard/second_withdrawal_approval.html'
    model = WithdrawalBatch
    paginate_by = 10
    context_object_name = 'batch_withdrawals'

    def get_queryset(self):
        tenant=self.request.tenant

        return WithdrawalBatch.objects.filter(
            tenant=tenant,
            first_approval=True,
            second_approval=False,
            third_approval=False,
            fourth_approval=False
        ).order_by('-date_created')
    
    def post(self,*args,**kwargs):
        tenant = self.request.tenant
        batch_id = self.request.POST.getlist('batch_id[]')
        print(batch_id)
        if not batch_id:
            return JsonResponse({
                'status':'error',
                'message':'Please select a batch to approve'
            })
        
        try:
            email = TenantEventNotification.objects.filter(
                tenant=tenant,
                event = 'withdrawal_second_approval'
            ).values_list('staff__email', flat=True)

            if not email:
                return JsonResponse({
                    'status':'error',
                    'message':'No event mapping found for this event: second level approval of withdrawal request.'
                })
        except Exception as e:
            logger.error(f'An error occured: {str(e)}')
            return JsonResponse({
                'status':'error',
                'message':f'An error occured.'
            })
        
        try:
            batches = WithdrawalBatch.objects.filter(
                id__in=batch_id,
                tenant=tenant,
                first_approval=True,
                second_approval=False,
                third_approval=False,
                fourth_approval=False
            )
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message':'No withdrawal batch matches the given batch ID.'
            })
        
        # Approve batch
        try:
            for batch in batches:
                batch.approve_batch(approval_level=2)
            # If level 2 approval is successful:

            # Notify level 3 for final approval
            subject = 'Withdrawal Approval'
            message = f'A withdrawal request has been initiated and awaiting your approval.'
            emails = list(email)
            gen_send_email.delay(
                subject=subject,
                message=message,
                recepient=emails
            )

            return JsonResponse({
                'status':'success',
                'message':'Withdrawal batch approved successfuly'
            })
        except ValueError as value_error:
            return JsonResponse({
                'status':'error',
                'message':f'{str(value_error)}'
            })
        except Exception as return_value:
            return JsonResponse(
                return_value # return_value is a an object returned from the model when approve_batch is called
            )

# Approval done through email link
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Supervisor']), name='dispatch')
class SecondPhaseOfWithdrawalApprovalEmail(TemplateView):
    template_name = 'dashboard/email_withdrawal_approval.html'
    def post(self, *args, **kwargs):
        tenant = self.request.tenant
        batch_id = self.request.POST.get('batch_id')

        if not batch_id:
            return JsonResponse({
                'status':'error',
                'message':'Invalid url'
            })
        
        try:
            batch = WithdrawalBatch.objects.get(
                id=batch_id,
                tenant=tenant,
                first_approval=True,
                second_approval=False,
                third_approval=False,
                fourth_approval=False
            )
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message':'No withdrawal batch matches the given batch ID.'
            })
        
        # Approve batch
        try:
            batch.approve_batch(approval_level=2)
            # If level 2 approval is successful:
            return JsonResponse({
                'status':'success',
                'message':'Withdrawal batch approved successfuly'
            })
        except ValueError as value_error:
            return JsonResponse({
                'status':'error',
                'message':f'{str(value_error)}'
            })
        except Exception as return_value:
            return JsonResponse(
                return_value # return_value is a an object returned from the model when approve_batch is called
            )
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant=self.request.tenant
        batch_id = self.kwargs['batch_id']

        context['batch'] = WithdrawalBatch.objects.get(
                id=batch_id,
                tenant=tenant,
                first_approval=True,
                second_approval=False,
                third_approval=False,
                fourth_approval=False
            )
        return context


@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Manager','Finance Supervisor','Finance Analyst']), name='dispatch')
class BatchWithdrawalListView(ListView):
    template_name = 'dashboard/batch_withdrawal_list.html'
    model = WithdrawalRequest
    paginate_by = 20
    context_object_name = 'withdrawals'

    def get_queryset(self):
        tenant = self.request.tenant
        batch_id = self.kwargs['batch_id']
        return WithdrawalRequest.objects.filter(
            tenant=tenant,
            parent_batch__id=batch_id
        )
    


# SECOND STAGE OF APPROVAL FOR WITHDRAWAL REQUEST THROUGH EMAIL
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Manager']), name='dispatch')
class ThirdPhaseOfWithdrawalApproval(ListView):
    template_name = 'dashboard/third_withdrawal_approval.html'
    model = WithdrawalBatch
    paginate_by = 10
    context_object_name = 'batch_withdrawals'

    def get_queryset(self):
        tenant=self.request.tenant

        return WithdrawalBatch.objects.filter(
            tenant=tenant,
            first_approval=True,
            second_approval=True,
            fourth_approval=False,
            third_approval=False
        ).order_by('-date_created')
    
    def post(self,*args,**kwargs):
        tenant = self.request.tenant
        batch_id = self.request.POST.getlist('batch_id[]')
        print(batch_id)
        if not batch_id:
            return JsonResponse({
                'status':'error',
                'message':'Please select a batch to approve'
            })
        
        try:
            email = TenantEventNotification.objects.filter(
                tenant=tenant,
                event = 'withdrawal_final_approval'
            ).values_list('staff__email', flat=True)

            if not email:
                return JsonResponse({
                    'status':'error',
                    'message':'No event mapping found for this event: final level approval of withdrawal request.'
                })
        except Exception as e:
            logger.error(f'An error occured: {str(e)}')
            return JsonResponse({
                'status':'error',
                'message':f'An error occured.'
            })
        
        try:
            batches = WithdrawalBatch.objects.filter(
                id__in=batch_id,
                tenant=tenant,
                first_approval=True,
                second_approval=True,
                third_approval=False,
                fourth_approval=False
            )
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message':'No withdrawal batch matches the given batch ID.'
            })
        
        # Approve batch
        try:
            for batch in batches:
                batch.approve_batch(approval_level=3)
            # If level 3 approval is successful:

            # Notify level 4 for final payout
            subject = 'Withdrawal Approval'
            message = f'A withdrawal request has been initiated and awaiting your approval.'
            emails = list(email)
            gen_send_email.delay(
                subject=subject,
                message=message,
                recepient=emails
            )

            return JsonResponse({
                'status':'success',
                'message':'Withdrawal batch approved successfuly'
            })
        except ValueError as value_error:
            return JsonResponse({
                'status':'error',
                'message':f'{str(value_error)}'
            })
        except Exception as return_value:
            return JsonResponse(
                return_value # return_value is a an object returned from the model when approve_batch is called
            )
        



@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Manager']), name='dispatch')
class FinalBatchWithdrawalApproval(ListView):
    template_name = 'dashboard/final_batch_withdrawal_approval.html'
    model = WithdrawalBatch
    paginate_by = 10
    context_object_name = 'batch_withdrawals'

    def get_queryset(self):
        tenant=self.request.tenant

        return WithdrawalBatch.objects.filter(
            tenant=tenant,
            first_approval=True,
            second_approval=True,
            third_approval=True,
            fourth_approval=False
        ).order_by('-date_created')
    
    def post(self,*args,**kwargs):
        tenant = self.request.tenant
        batch_id = self.request.POST.getlist('batch_id[]')
        mode_of_payment = self.request.POST.get('payment_mode')
        bank_id = self.request.POST.get('bank_id')
        print(batch_id)
        if not batch_id:
            return JsonResponse({
                'status':'error',
                'message':'Please select a batch to approve'
            })
        
        if not mode_of_payment:
            return JsonResponse({
                'status':'error',
                'message':'Please select mode of payment'
            })
        
        bank = None
        if mode_of_payment == 'Bank Transfer' and bank_id:
            try:
                bank = BankAccount.objects.get(
                    id=bank_id,
                    tenant=tenant
                )
            except ObjectDoesNotExist:
                return JsonResponse({
                    'status':'error',
                    'message':'Bank not found.'
                })
        else:
            bank = None
        
        try:
            batches = WithdrawalBatch.objects.filter(
                id__in=batch_id,
                tenant=tenant,
                first_approval=True,
                second_approval=True,
                third_approval=True,
                fourth_approval=False
            )
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message':'No withdrawal batch matches the given batch ID.'
            })
        
        # Approve batch
        try:
            now = timezone.now()
            for batch in batches:
                batch.bank = bank
                batch.mode_of_payment = mode_of_payment
                batch.approve_batch(approval_level=4)
                batch.save()
            # If level 4 approval is successful:
            # create transaction object for individual requests
            all_transactions = []
            withdrawals = batch.withdrawal_request.all()

            for withdrawal in withdrawals:
                member_transaction = Transaction(
                    id=generate_short_alpha_numeric_id(Transaction),
                    tenant=tenant,
                    staff=withdrawal.staff,
                    scheme = withdrawal.scheme,
                    transaction_date=now,
                    transaction_type='General Payout',
                    payment_method='Bank Transfer',
                    amount=withdrawal.amount
                )
                all_transactions.append(member_transaction)
            
            # Bulk create transactions
            try:
                with transaction.atomic():
                    # create transactions
                    Transaction.objects.bulk_create(
                        all_transactions
                    )
            except Exception as e:
                logger.info(f'An error occured while creating transactions for general payout: {e}')

            # Call Task to send sheet to bank for payment processing
            
            send_excel_sheet_to_bank_for_payment.delay(batch_id)

            return JsonResponse({
                'status':'success',
                'message':f'Batch approved for Payment. Bank will be instructed to make payment.'
            })
        except ValueError as value_error:
            return JsonResponse({
                'status':'error',
                'message':f'{str(value_error)}'
            })
        except Exception as return_value:
            return JsonResponse(
                return_value # return_value is a an object returned from the model when approve_batch is called
            )
    
    def get_context_data(self, **kwargs):
        tenant = self.request.tenant
        context = super().get_context_data(**kwargs)
        context['banks'] = BankAccount.objects.filter(
            tenant=tenant
        )
        context['mode_of_payment'] = Transaction.payment_method_choices
        return context


# Add Schedule Payment Date
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Scheme Analyst','Scheme Supervisor','Scheme Manager']), name='dispatch')
class SchedulePaymentDateView(TemplateView):
    template_name = 'dashboard/schedule_payment_date.html'

    def post(self,*args,**kwargs):
        tenant = self.request.tenant
        scheme_id = self.request.POST.get('scheme_id')
        bank_id = self.request.POST.get('bank')
        day = self.request.POST.get('payment_day')
        month = self.request.POST.get('payment_month')
        payout_percentage = self.request.POST.get('payout_percentage')

        if not all([scheme_id,day,month,bank_id]):
            return JsonResponse({
                'status':'error',
                'message':'Missing required fields'
            })
        
        # Validate days for February
        if int(month) == 2 and int(day) > 29:
            return JsonResponse({
                'status':'error',
                'message':'Selected day out of range.'
            })
        
        try:
            scheme = InvestmentScheme.objects.get(
                id=scheme_id,
                tenant=tenant,
                approved=True
            )
        except ObjectDoesNotExist:
            return JsonResponse({
                'status':'error',
                'message':'Scheme not found'
            })

        try:
            bank = BankAccount.objects.get(
                tenant=tenant,
                id=bank_id
            )
        except ObjectDoesNotExist:
            return JsonResponse({
                'status':'error',
                'message':'Bank not found'
            })
        
        # Create schedule date object
        try:
            ScheduledPaymentDates.objects.create(
                tenant=tenant,
                scheme=scheme,
                bank=bank,
                day=day,
                month=month,
                payout_percentage=Decimal(payout_percentage),
            )

            # Send Email notification for date approval of schedule payment dates
            # gen_send_email(
                #recepient
                #message
                #subject
            # )
            return JsonResponse({
                'status':'success',
                'message':'Date added successfully.'
            })
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message':f'Operation can not be performed at this time. {str(e)}'
            })
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant

        if tenant:
            try:
                schemes = InvestmentScheme.objects.filter(
                    tenant=tenant,
                    approved=True
                ).prefetch_related('scheduledPaymentDate').order_by('-created_date')
                # print(f'Payout Dates: {schemes.scheduledPaymentDate}')
            except InvestmentScheme.DoesNotExist:
                schemes = None
            
            try:
                banks = BankAccount.objects.filter(
                    tenant=tenant
                )
            except BankAccount.DoesNotExist:
                banks = None
            
            context['available_schemes'] = schemes
            context['banks'] = banks
            context['months'] = ScheduledPaymentDates.month_choices
            context['payment_days'] = range(1,32) #1st to 31st
        return context
    

# Approve Scheduled Payment Date
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Scheme Manager']), name='dispatch')
class ApproveScheduledPaymentDateView(View):
    def post(self,*args,**kwargs):
        tenant = self.request.tenant
        scheduled_date_id = self.kwargs['date_id']

        if not scheduled_date_id:
            return JsonResponse({
                'status':'error',
                'message':'Invalid date selected.'
            })
        
        # Get date and approve
        try:
            date = ScheduledPaymentDates.objects.get(
                tenant=tenant,
                id=scheduled_date_id
            )
            date.approved = True #Approve date
            date.save() #save date object

            return JsonResponse({
                'status':'success',
                'message':'Date approved successfully.'
            })
        except ObjectDoesNotExist:
            return JsonResponse({
                'status':'error',
                'message':'Can not find date object.'
            })
        except Exception as e:
            logger.info(f'An error occured fetching scheduled date: {e}')
            return JsonResponse({
                'status':'error',
                'message':'Internal server error.'
            },status=500)


# PAUSE SCHEDULE PAYOUT
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Scheme Manager']), name='dispatch')
class PauseScheduledPaymentDateView(View):
    def get(self, request, *args, **kwargs):

        tenant = self.request.tenant
        payment_date_id = self.kwargs['schedule_date_id']

        if not payment_date_id:
            return JsonResponse({
                'status':'error',
                'message':'Invalid scheduled date ID.'
            })
        
        try:
            scheduled_date = ScheduledPaymentDates.objects.get(
                tenant=tenant,
                id = payment_date_id
            )
            scheduled_date.approved = False
            scheduled_date.save()
            return JsonResponse({
                'status':'success',
                'message':'Date paused successfully.'
            })
        except ObjectDoesNotExist:
            return JsonResponse({
                'status':'error',
                'message':'Scheduled date not found.'
            })
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message':f'An error occured: {str(e)}'
            })



@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Scheme Supervisor']), name='dispatch')
class DeleteSchedulePaymentDate(DeleteView):
    model = ScheduledPaymentDates
    
    def get_queryset(self):
        tenant = self.request.tenant

        return ScheduledPaymentDates.objects.filter(tenant=tenant)
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            self.object.delete()
            return JsonResponse({
                'status':'success',
                'message':'Scheduled date deleted successfully.'
            })
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message':f'An error occured: {str(e)}'
            })


# SUPPLIERS VIEW
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Manager','Finance Supervisor','Finance Analyst']), name='dispatch')
class SupplierView(TemplateView):
    template_name = 'suppliers_expenses/suppliers.html'

    def post(self,*args,**kwargs):
        tenant = self.request.tenant
        supplier_name = self.request.POST.get('supplier_name')
        supplier_address = self.request.POST.get('supplier_address')
        supplier_phone = self.request.POST.get('supplier_phone')
        supplier_email = self.request.POST.get('supplier_email')
        supplier_bank = self.request.POST.get('supplier_bank')
        supplier_account = self.request.POST.get('supplier_account')
        supplier_branch = self.request.POST.get('supplier_branch')

        if not all([supplier_account,supplier_address,supplier_bank,supplier_branch,supplier_email,supplier_name,supplier_phone]):
            return JsonResponse({
                'status':'error',
                'message':'Missing required fields.'
            })
        
        if not tenant:
            return JsonResponse({
                'status':'error',
                'message':'Invalid Tenant'
            })
        
        try:
            Suppliers.objects.create(
                tenant=tenant,
                name=supplier_name,
                bank=supplier_bank,
                account_number=supplier_account,
                email=supplier_email,
                phone=supplier_phone,
                address=supplier_address,
                branch=supplier_branch
            )
            return JsonResponse({
                'status':'success',
                'message':'Success'
            })
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message':f'An error occured: {str(e)}'
            })

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant

        # Fetch all suppliers related to tenant
        try:
            suppliers = Suppliers.objects.filter(
                tenant=tenant
            )
            context['suppliers'] = suppliers
        except Exception:
            suppliers = Suppliers.objects.none()
            context['suppliers'] = suppliers
        
        return context



# DELETE SUPPLIER
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Analyst']), name='dispatch')
class DeleteSupplierView(DeleteView):
    model = Suppliers

    def get_queryset(self):
        tenant = self.request.tenant
        return Suppliers.objects.filter(tenant=tenant)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        supplier_name = self.object.name

        try:
            self.object.delete()
            return JsonResponse({
                'status': 'success',
                'message': f'{supplier_name} deleted successfully'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'An error occurred: {str(e)}'
            })



# UPDATE SUPPLIER DETAILS
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Analyst']), name='dispatch')
class UpdateSupplierView(UpdateView):
    model = Suppliers
    fields = [
        'name',
        'address',
        'phone',
        'bank',
        'account_number',
        'email',
        'branch'
    ]

    def get_queryset(self):
        tenant = self.request.tenant
        return Suppliers.objects.filter(tenant=tenant)

    def form_valid(self, form):
        try:
            self.object = form.save()
            return JsonResponse({
                'status': 'success',
                'message': 'Supplier updated successfully.'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'An error occurred: {str(e)}'
            })

    def form_invalid(self, form):
        return JsonResponse({
            'status': 'error',
            'message': 'Form submission is invalid.',
            'errors': form.errors
        })


# Supplier Search View
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Manager','Finance Supervisor','Finance Analyst']), name='dispatch')
class SupplierSearchView(View):
    def get(self,request,*args,**kwargs):
        tenant = self.request.tenant
        search_term = self.request.GET.get('search_term')

        if not search_term:
            return JsonResponse({
                'status':'error',
                'message':'Search term required.'
            },status=400)
        
        suppliers = Suppliers.objects.filter(
            Q(name__icontains=search_term)|
            Q(bank__icontains=search_term)|
            Q(email__icontains=search_term)|
            Q(phone__icontains=search_term),
            tenant=tenant
        )

        suppliers_list = [
            {
                'id':supplier.id,
                'name':supplier.name,
                'bank':supplier.bank,
                'address':supplier.address,
                'phone':supplier.phone,
                'email':supplier.email,
                'branch':supplier.branch,
                'account_number':supplier.account_number
            }
            for supplier in suppliers
        ]
        return JsonResponse({
            'status':'success',
            'suppliers':suppliers_list
        })




# RAISE REQUISITION VIEW
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Analyst','Finance Supervisor','Finance Manager']), name='dispatch')
class RaiseRequisitionView(TemplateView):
    template_name = 'suppliers_expenses/create_requisition.html'

    def post(self,*args,**kwargs):
        tenant = self.request.tenant
        supplier_id = self.request.POST.get('supplier_id')
        description = self.request.POST.get('description')

        if not all([supplier_id,description]):
            return JsonResponse({
                'status':'error',
                'message':'Missing required fields.'
            })

        try:
            supplier = Suppliers.objects.get(
                tenant=tenant,
                id=supplier_id
            )
        except ObjectDoesNotExist:
            return JsonResponse({
                'status':'error',
                'message':'Supplier not found.'
            })
        
        try:
            Requisition.objects.create(
                tenant=tenant,
                supplier=supplier,
                description=description
            )
            return JsonResponse({
                'status':'success',
                'message':'Requisition created.'
            })
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message':f'An error occured saving requisition: {str(e)}'
            })

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        if tenant:
            try:
                suppliers = Suppliers.objects.filter(tenant=tenant)
            except Suppliers.DoesNotExist:
                suppliers = None
            
            try:
                requisitions = Requisition.objects.filter(
                    tenant=tenant,
                    approved=False
                )
            except Requisition.DoesNotExist:
                requisitions = None

        context['suppliers'] = suppliers
        context['requisition_headers'] = requisitions

        return context


# UPDATE TAX ON REQUISITION
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Analyst']), name='dispatch')
class UpdateTaxOnRequisition(View):
    def post(self,*args,**kwargs):
        tenant = self.request.tenant
        req_id = self.kwargs.get('req_id')
        tax_amount = self.request.POST.get('tax')
        if not req_id:
            return JsonResponse({
                'status':'error',
                'message':'Invalid requisition ID.'
            })
        
        requisition = Requisition.objects.filter(
            id=req_id,
            tenant=tenant
        ).first()

        if not requisition:
            return JsonResponse({
                'status':'error',
                'message':'Requisition not found.'
            })
        
        requisition.tax_amount = Decimal(tax_amount)
        requisition.save()

        return JsonResponse({
            'status':'success',
            'message':'Tax added successfully.',
            'tax_amount':Decimal(tax_amount)
        })




# ADD REQUISITION ITEM VIEW MODAL
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Analyst']), name='dispatch')
class AddRequisitionItemView(CreateView):
    model = RequisitionItem
    fields = ('item_name','quantity','amount')

    def form_valid(self, form):
        tenant = self.request.tenant
        requisition_id = self.request.POST.get('requisition_id')

        if not requisition_id:
            return JsonResponse({
                'status':'error',
                'message':'Please select a requisition'
            })
        try:
            requisition = Requisition.objects.get(
                tenant=tenant,
                id=requisition_id
            )
        except ObjectDoesNotExist:
            return JsonResponse({
                'status':'error',
                'message':'Requisition not found'
            })
        # Dont allow addition to approved requisitions
        if requisition.approved == True:
            return JsonResponse({
                'status':'error',
                'message':'Can not add new item to an approved requisition'
            })
        try:
            form.instance.requisition = requisition
            form.save()
        
            return JsonResponse({
                'status':'success',
                'message':'Item added',
                'total_amount':requisition.total_amount
            })
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message':f'An error occured saving item: {str(e)}'
            })
    
    def form_invalid(self, form):
        return JsonResponse({
            'status':'error',
            'message':f'Invalid Form Data: {str(form.errors)}'
        })

    def get_success_url(self):
        tenant = self.request.tenant
        url = reverse('raise_requisition', kwargs={'tenant_id':tenant.id})
        return url



# FETCH REQUISITION ITEMS When viewing PO
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Manager','Finance Supervisor','Finance Analyst']), name='dispatch')
class FetchItemsView(View):
    def get(self,*args,**kwargs):
        tenant = self.request.tenant
        req_id = self.kwargs['req_id']

        if not req_id:
            return JsonResponse({
                'status':'error',
                'message':'Invalid requisition selected.'
            })

        try:
            requisition =  Requisition.objects.filter(id=req_id,tenant=tenant).prefetch_related('items').first()
            items = requisition.items.all()
            items_list = []

            for item in items:
                items_list.append({
                    'id':item.id,
                    'item_name':item.item_name,
                    'quantity':item.quantity,
                    'amount':item.amount,
                    'total_cost':item.total_cost
                })
            return JsonResponse({
                'status':'success',
                'items':items_list,
                'total_amount':requisition.total_amount,
                'tax_amount':requisition.tax_amount if requisition else 0.00
            })
        except ObjectDoesNotExist:
            return JsonResponse({
                'status':'error',
                'message':'Requisition does not exist.'
            })



# DELETE REQUISITION OBJECT VIEW
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Analyst']), name='dispatch')
class DeleteRequisitionView(DeleteView):
    model = Requisition

    def get_queryset(self):
        tenant = self.request.tenant
        return Requisition.objects.filter(tenant=tenant)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()

        if not self.object:
            return JsonResponse({
                'status':'error',
                'message':'Requisition not found.'
            })
        name = self.object.description
        try:
            self.object.delete()
            return JsonResponse({
                'status':'success',
                'message':f'{name} deleted.'
            })
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message':f'An error occured while trying to delete {name}'
            })



# DELETE REQUISITION ITEM VIEW
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Analyst']), name='dispatch')
class DeleteRequisitionItemView(DeleteView):
    model = RequisitionItem

    def get_queryset(self):
        tenant = self.request.tenant
        requisition_id = self.kwargs['req_id']
        requisition = Requisition.objects.get(
            tenant=tenant,
            id=requisition_id
        )

        return RequisitionItem.objects.filter(
            requisition=requisition
        )

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()

        if not self.object:
            return JsonResponse({
                'status':'error',
                'message':'Item not found.'
            })
        name = self.object.item_name
        requisition = self.object.requisition
        # Prevent removing an item from an approved requisition
        if self.object.requisition.approved == True:
            return JsonResponse({
                'status':'error',
                'message':'Can not remove item from an approved requisition.'
            })
        try:
            self.object.delete()
            return JsonResponse({
                'status':'success',
                'message':f'{name} deleted.',
                'total_amount':requisition.total_amount
            })
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message':f'An error occured while trying to delete {name}'
            })




# APPROVE REQUISITION VIEW
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Manager']), name='dispatch')
class ApproveRequisitionView(View):
    def post(self,*args,**kwargs):
        tenant = self.request.tenant
        requisition_id = self.kwargs['req_id']

        if not requisition_id:
            return JsonResponse({
                'status':'error',
                'message':'Please select a requisition'
            })
        
        try:
            requisition = Requisition.objects.get(
                tenant=tenant,
                id=requisition_id
            )
        except ObjectDoesNotExist:
            return JsonResponse({
                'status':'error',
                'message':'No matching Requisition found'
            })
        
        # Approve Requisition
        try:
            requisition.approve()
            return JsonResponse({
                'status':'success',
                'message':f'{requisition.description}Approve successfully'
            })
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message':f'An error occured: {str(e)}'
            })





# PURCHASE ORDER VIEW
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Manager','Finance Supervisor','Finance Analyst']), name='dispatch')
class PurchaseOrderView(ListView):
    model = PurchaseOrder
    template_name = 'suppliers_expenses/purchase_order.html'
    context_object_name = 'purchase_orders'
    paginate_by = 6
    
    def get_queryset(self):
        tenant = self.request.tenant
        return PurchaseOrder.objects.filter(
            requisition__tenant=tenant,
            requisition__approved=True
        )
    
    # Order Received
    def post(self,*args,**kwargs):
        # tenant = self.request.tenant
        order_id = self.kwargs.get('order_id')
        list_of_item_ids = self.request.POST.getlist('item_id[]')
        list_of_received_quantity = self.request.POST.getlist('received_quantity[]')
        tax = self.request.POST.get('tax')

        if not order_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid order ID.'
            })
        
        if not tax:
            return JsonResponse({
                'status':'error',
                'message':'Please input tax amount.'
            })

        if not all(list_of_received_quantity):
            return JsonResponse({
                'status':'error',
                'message':'Please make sure you fill in the matching received quantity field for each item'
            })

        try:
            order = self.get_queryset().get(
                id=order_id
            )

            # check if remaining items is less than expected received items
            received_object = ReceivedItems.objects.filter(
                purchase_order=order
            ).first()

            if received_object and received_object.number_of_items_remaining < sum(int(a) for a in list_of_received_quantity):
                return JsonResponse({
                    'status':'error',
                    'message':'Total remaining items do not match your provided quantity.'
                })


            if order.received == True:
                return JsonResponse({
                    'status':'error',
                    'message':'This order is already received'
                })
            

            # Compare original quantity against received quantity
            # get all order items from db
            items = order.requisition.items.all()

            # amount list: holds cash amount of received items
            amount_list = []
            if items:
                for item_id, received_quantity in zip(list_of_item_ids, list_of_received_quantity):
                    
                    try:
                        item = items.get(id=item_id) 
                        if (int(received_quantity) > item.quantity):
                            return JsonResponse({
                                'status': 'error',
                                'message': 'Received quantity cannot exceed ordered quantity.'
                            })
                        # Append amount to amount list
                        amount_list.append(
                            (item.amount * int(received_quantity))
                        )
                    except Exception as e:
                        return JsonResponse({
                            'status': 'error',
                            'message': f'Item with ID {item_id} not found in the order items.'
                        })
                    
                """""
                Updating ReceivedItems 
                """""
                # check for received_items for order if any exist else create one
                
                if received_object:
                    received_items = received_object
                else: #If this is the first time receiving, create received_items
                    received_items = ReceivedItems.objects.create(
                        purchase_order=order
                    )
                total_quantity_received = sum(int(q) for q in list_of_received_quantity)
                    
                # Update number of received items
                received_items.number_of_items_received += total_quantity_received
                # update balance left tax included
                amount = sum(Decimal(a) for a in amount_list) + Decimal(tax)
                received_items.balance -= amount
                # Update the amount_to_pay field
                received_items.amount_to_pay += amount

                # save changes
                received_items.save()
            else:
                return JsonResponse({
                    'status':'error',
                    'message':'No items found for this order.'
                })
            
            return JsonResponse({
                'status':'success',
                'message':'Proceed to invoice payment.'
            })
        except ObjectDoesNotExist as e:
            return JsonResponse({
                'status':'error',
                'message':f'Order does not exist. {e}'
            })





# FETCH REQUISITION ITEMS FOR A SPECIFIC PO
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Manager','Finance Supervisor','Finance Analyst']), name='dispatch')
class FetchPurchaseOrderView(View):
    def get(self,*args,**kwargs):
        tenant = self.request.tenant
        order_id = self.kwargs['order_id']

        if not order_id:
            return JsonResponse({
                'status':'error',
                'message':'Invalid purchase order selected.'
            })
        
        try:
            order =  PurchaseOrder.objects.get(
                requisition__tenant=tenant,
                id=order_id
            )
            received_items = ReceivedItems.objects.filter(
                purchase_order=order
            )
            items = order.requisition.items.all()
            items_list = []

            for item in items:
                items_list.append({
                    'id':item.id,
                    'item_name':item.item_name,
                    'quantity':item.quantity,
                    'amount':item.amount,
                    'total_cost':item.total_cost,
                    'order_id':order_id,
                })
            return JsonResponse({
                'status':'success',
                'items':items_list,
                'total_amount':order.amount,
                'order_received':order.received,
                'balance':received_items.first().balance if received_items.exists() else order.amount,
                'tax_amount':order.requisition.tax_amount,
            })
        except ObjectDoesNotExist:
            return JsonResponse({
                'status':'error',
                'message':'Purchase order does not exist.'
            })


# PURCHASE SPECIFIC ORDER SEARCH
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Manager','Finance Supervisor','Finance Analyst']), name='dispatch')
class PurchaseOrderSearchView(View):

    def get(self,request,*args,**kwargs):
        search_term = self.request.GET.get('search_term')
        tenant = self.request.tenant

        if not search_term:
            return JsonResponse({
                'status':'error',
                'message':'Search term required.'
            })
        
        try:
            orders = PurchaseOrder.objects.filter(
                Q(id__icontains=search_term)|
                Q(requisition__supplier__name__icontains=search_term)|
                Q(requisition__description__icontains=search_term),
                requisition__tenant=tenant
            )
               
            order_list = [
                {
                    'id':order.id,
                    'supplier':order.requisition.supplier.name,
                    'total_amount':order.amount,
                    'date_created':order.date_created,
                    'status':order.received,
                    'description':order.requisition.description
                }
                for order in orders
            ]
            
            return JsonResponse({
                'status':'success',
                'orders':order_list
            })
        except Exception as e:
            logger.error(f'{e}')
            return JsonResponse({
                'status':'error',
                'message':'Order not found.'
            }) 
    
    


# CREATE INVOICE VIEW
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Analyst']), name='dispatch')
class CreateInvoiceView(TemplateView):
    template_name = 'suppliers_expenses/create_invoice.html'

    def post(self,*args,**kwargs):
        tenant =  getattr(self.request,'tenant',None)
        order_id = self.request.POST.get('order_number')
        supplier_invoice_amount = self.request.POST.get('supplier_invoice_amount')
        debit_account_id = self.request.POST.get('debit_account_id')

        if not tenant or not self.request.user:
            return JsonResponse({
                'status': 'error',
                'message': 'Bad request.'
            })

        if not debit_account_id:
            return JsonResponse({
                'status':'error',
                'message':'Selected account has no ID.'
            })
        
        if not order_id:
            return JsonResponse({
                'status':'error',
                'message':'Invalid order ID.'
            })

        if not AccountMapping.objects.filter(
                tenant=tenant,
                name='Supplier Invoice Creation'
            ).exists():
            return JsonResponse({
                'status':'error',
                'message':'Mapping for "Supplier Invoice Creation" not found.'
            })
        

        debit_account = ChartOfAccounts.objects.filter(
                tenant=tenant,
                id=debit_account_id
            ).first()
        credit_account = AccountMapping.objects.filter(
                tenant=tenant,
                name='Supplier Invoice Creation'
            ).first().credit_acc

        if not debit_account and not credit_account:
            return JsonResponse({
                'status':'error',
                'message':'Debit or Credit account not found. Please map accounts and try again.'
            })

        
        try:
            purchase_order = PurchaseOrder.objects.filter(
                requisition__tenant=tenant,
                id=order_id,
            ).first()

            if not purchase_order:
                return JsonResponse({
                    'status':'error',
                    'message':'Purchase order not found.'
                })

            # check if the requested amount is less than the amount to be paid
            received_items_object = purchase_order.received_items
            if not received_items_object:
                return JsonResponse({
                    'status':'error',
                    'message':'This purchase order has not been received yet.'
                })
            
            if Decimal(supplier_invoice_amount) > received_items_object.amount_to_pay:
                return JsonResponse({
                    'status':'error',
                    'message':'Supplier amount cannot be greater than the expected amount to pay.'
                })
            
            # Create invoice on system to be used for payment
            try:
                PaymentInvoice.objects.create(
                    invoice_number=generate_purchase_invoice_number(PaymentInvoice),
                    purchase_order=purchase_order,
                    amount=Decimal(supplier_invoice_amount),
                    supplier=purchase_order.requisition.supplier,
                    debit_account = debit_account
                )
                # Update amount_to_pay field by subtracting invoice amount to be paid
                received_items_object.amount_to_pay -= Decimal(supplier_invoice_amount)
                # Save update
                received_items_object.save()

                # Debit and Credit operations
                accounting_service = AccountingService(tenant=tenant,user=self.request.user,scheme=None)
                try:
                    accounting_service.create_manual_entry(debit_account,credit_account,Decimal(supplier_invoice_amount))
                except ValidationError as e:
                    return JsonResponse({
                        'status':'error',
                        'message':f'An error occurred while creating manual entry: {str(e)}'
                    })

                #TODO Notify who is in charge of invoice payment.

                return JsonResponse({
                    'status':'success',
                    'message':'Invoice created successfully. Payment will be initiated once invoice is cleared.'
                })
            except Exception as e:
                logger.info(f'An error occurred while creating an invoice for Tenant: {tenant} Purchase Order: {purchase_order.id} || Error: {str(e)}')
                return JsonResponse({
                    'status':'error',
                    'message':f'Invoice could not be created now, please try again later and contact Admin if issue persists.'
                })

        except ObjectDoesNotExist:
            return JsonResponse({
                'status':'error',
                'message':'Purchase order does not exist.'
            })
        except Exception as e:
            logger.info(f'An error occured: {str(e)}')
            print(f'An error occured: {str(e)}')
            return JsonResponse({
                'status':'error',
                'message':f'A server side error occured. {str(e)}'
            })

@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Manager']), name='dispatch')
class InvoiceApproval(ListView):
    model = PaymentInvoice
    template_name = 'suppliers_expenses/approve_invoice.html'
    context_object_name = 'invoice_list'
    paginate_by = 5
    def get_queryset(self):
        tenant = self.request.tenant
        return PaymentInvoice.objects.filter(
            purchase_order__requisition__tenant=tenant,
            # approved=False,
            paid=False
        ).order_by('approved','-created_date')

    def post(self,*args,**kwargs):
        invoice_number = self.request.POST.get('invoice_number')

        if not invoice_number:
            return JsonResponse({
                'status':'error',
                'message':'Invalid or no invoice number found.'
            })
        
        try:
            invoice = self.get_queryset().get(
                invoice_number=invoice_number
            )
        except ObjectDoesNotExist:
            return JsonResponse({
                'status':'error',
                'message':'Invoice not found.'
            })
        except Exception as e:
            logger.info(f'An error occured while fetching invoice: {str(e)}')
            return JsonResponse({
                'status':'error',
                'message':f'An error occured {str(e)}'
            })

        invoice.approved =True
        invoice.save()

        return JsonResponse({
            'status':'success',
            'message':f'Invoice with number: {invoice_number} approved successfully'
        })
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        total_invoice_count = queryset.count()
        pending_count = queryset.filter(approved=False).count()
        approved_count = (total_invoice_count-pending_count)
        context['total_count'] = total_invoice_count
        context['approved_count'] = approved_count
        context['pending_count'] = pending_count
        return context
        


# Search for Invoice: Invoice Payment Page
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Manager']), name='dispatch')
class ApproveInvoiceSearchView(View):
    def get(self,request,*args,**kwargs):
        tenant = self.request.tenant
        search_term = self.request.GET.get('search_term')

        if not search_term:
            return JsonResponse({
                'status':'error',
                'message':'Search term required'
            },status=400)
        
        invoices = PaymentInvoice.objects.filter(
            Q(invoice_number__icontains=search_term)|
            Q(purchase_order__id__icontains=search_term)|
            Q(supplier__name__icontains=search_term)|
            Q(debit_account__name__icontains=search_term)|
            Q(purchase_order__requisition__description__icontains=search_term),
            purchase_order__requisition__tenant=tenant,
            paid=False
        )

        invoice_list = [
            {
                'invoice_number':invoice.invoice_number,
                'description':invoice.purchase_order.requisition.description,
                'supplier':invoice.supplier.name,
                'amount':invoice.amount,
                'created_date':invoice.created_date,
                'debit_account':invoice.debit_account.name if invoice.debit_account else None,
                'paid':invoice.paid
            }
            for invoice in invoices
        ]
        return JsonResponse({
            'status':'success',
            'invoices':invoice_list
        })






@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Analyst']), name='dispatch')
class PayoutInvoiceView(ListView):
    model = PaymentInvoice
    template_name = 'suppliers_expenses/payout_invoice.html'
    paginate_by = 5
    context_object_name = 'invoice_list'

    def get_queryset(self):
        tenant = getattr(self.request,'tenant',None)
        return super().get_queryset().filter(
            purchase_order__requisition__tenant = tenant,
            approved = True,
            # paid = False,
        ).order_by('paid','-created_date')

    def post(self,*args,**kwargs):
        tenant = getattr(self.request,'tenant',None)
        invoice_number = self.request.POST.get('invoice_number')
        withholding_tax = self.request.POST.get('withholding_tax')

        if not tenant or not self.request.user:
            return JsonResponse({
                'status': 'error',
                'message': 'Bad request.'
            })

        if not invoice_number:
            return JsonResponse({
                'status':'error',
                'message':'Invalid or no invoice number found'
            })
        
        if not withholding_tax:
            return JsonResponse({
                'status':'error',
                'message':'Please enter a withholding tax amount'
            })
        
        # convert tax amount to decimal value
        withholding_tax = Decimal(withholding_tax)
        

        invoice = self.get_queryset().filter(
                invoice_number=invoice_number
        ).first()

        if not invoice:
            return JsonResponse({
                'status':'error',
                'message':'Invoice not found.'
            })
        
        # Perform debit and credit transactions: if successful update invoice to paid
        account_mapping = AccountMapping.objects.filter(
            tenant=tenant,
            name="Supplier Invoice Payment"
        ).first()

        if not account_mapping:
            return JsonResponse({
                'status':'error',
                'message':'No account mapping found for this. Map this event and try again.'
            })

        # Calculate Net amount 
        net_amount = (invoice.amount - withholding_tax)

        # Perform debit and credit transactions
        with transaction.atomic():

            # Set withholding tax amount on the invoice
            invoice.withholding_tax = withholding_tax

            invoice.paid = True
            invoice.date_paid = timezone.now()
            invoice.save()

            #TODO Create a Transaction for the payment

            accounting_service = AccountingService(tenant=tenant,user=self.request.user,scheme=None)
            action_name = 'Supplier Invoice Payment'
            description = 'Invoice Payment'
            try:
                accounting_service.create_entry(action_name,net_amount,description)
            except ValidationError as e:
                return JsonResponse({
                    'status':'error',
                    'message':f'{e}'
                })
        return JsonResponse({
            'status':'success',
            'message':f'Invoice paid. Net amount = {net_amount}'
        })
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        pending_invoices = self.get_queryset().filter(paid=False).count()
        all_invoice = self.get_queryset().count
        context['pending_invoices'] = pending_invoices
        context['invoice_count'] = all_invoice
        return context


# Search for Invoice: Invoice Payment Page
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Analyst']), name='dispatch')
class PayoutInvoiceSearchView(View):
    def get(self,request,*args,**kwargs):
        tenant = self.request.tenant
        search_term = self.request.GET.get('search_term')

        if not search_term:
            return JsonResponse({
                'status':'error',
                'message':'Search term required'
            },status=400)
        
        invoices = PaymentInvoice.objects.filter(
            Q(invoice_number__icontains=search_term)|
            Q(purchase_order__id__icontains=search_term)|
            Q(supplier__name__icontains=search_term)|
            Q(debit_account__name__icontains=search_term),
            purchase_order__requisition__tenant=tenant,
            approved=True
        )

        invoice_list = [
            {
                'invoice_number':invoice.invoice_number,
                'description':invoice.purchase_order.requisition.description,
                'supplier':invoice.supplier.name,
                'amount':invoice.amount,
                'created_date':invoice.created_date,
                'debit_account':invoice.debit_account.name if invoice.debit_account else None,
                'paid':invoice.paid
            }
            for invoice in invoices
        ]
        return JsonResponse({
            'status':'success',
            'invoices':invoice_list
        })



@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Analyst']), name='dispatch')
class FetchPurchaseOrderForPayment(View):
    def get(self,*args,**kwargs):
        order_id = self.kwargs.get('order_id')
        tenant = self.request.tenant

        if not order_id:
            return JsonResponse({
                'status':'error',
                'message':'Invalid order ID'
            })
        if not tenant:
            return JsonResponse({
                'status':'error',
                'message':'An error occured'
            })
        
        # Fetch Assets/Expense accounts for tenant
        assets_or_expense_accounts = list(
            ChartOfAccounts.objects.filter(
                tenant=tenant,
                account_type__in=['EXPENSE','ASSET'],
                account_status='ACTIVE'
            ).values('id','account_code','name')
        )

        try:
            purchase_order = PurchaseOrder.objects.filter(
                id=order_id,
                requisition__tenant=tenant,
            ).first()

            if not purchase_order:
                return JsonResponse({
                    'status':'error',
                    'message':'No order matches the provided ID.'
                })
            
            return JsonResponse({
                'status':'success',
                'order_number':purchase_order.id,
                'supplier':purchase_order.requisition.supplier.name,
                'total_order_amount':purchase_order.amount,
                'amount_to_pay':purchase_order.received_items.amount_to_pay,
                'accounts':assets_or_expense_accounts
            })
        except Exception as e:
            logger.info(f'An error occured: {str(e)}')
            return JsonResponse({
                'status':'error',
                'message':f'Purchase order not found. {str(e)}'
            })
        



# PAYMENT HISTORY
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Finance Manager','Finance Supervisor','Finance Analyst']), name='dispatch')
class PaymentHistoryView(ListView):
    model = Transaction
    template_name = 'dashboard/payment_history.html'
    paginate_by = 15
    context_object_name='transaction_queryset'

    def get_queryset(self):
        tenant = self.request.tenant
        scheme_id = self.request.GET.get('scheme')
        payment_type = self.request.GET.get('payment_type')
        payment_method = self.request.GET.get('payment_method')
        status = self.request.GET.get('status')
        transaction_id = self.request.GET.get('transaction_id')

        # Start with an empty queryset if no scheme is provided
        queryset = Transaction.objects.filter(tenant=tenant).order_by('-transaction_date')

        # Apply additional filters if applicable
        filters = {}
        if scheme_id:
            filters['scheme__id'] = scheme_id
        if payment_type:
            filters['transaction_type'] = payment_type
        if payment_method:
            filters['payment_method'] = payment_method
        if transaction_id:
            filters['id']=transaction_id
        if status:
            filters['status'] = status

        # Apply all filters to the queryset
        if filters:
            # Unpack filters
            queryset = queryset.filter(**filters)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = self.request.GET.get('page',1)
        start_index = (int(page) - 1) * self.paginate_by + 1
        context.update({
            # 'transaction_queryset': queryset,
            'payment_methods': Transaction.payment_method_choices,
            'payment_status': Transaction.STATUS_CHOICES,
            'payment_type': Transaction.transaction_type_choices,
            'start_index':start_index,
            'results_count':self.get_queryset().count()
        })
        return context



@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Super User']), name='dispatch')
class EventMapping(ListView):
    model = TenantEventNotification
    template_name = 'dashboard/event_mapping.html'
    context_object_name = 'event_mapping'

    def get_queryset(self):
        tenant = self.request.tenant
        return TenantEventNotification.objects.filter(
            tenant=tenant
        ).order_by('-date_assigned')

    def post(self,*args,**kwargs):
        tenant = self.request.tenant
        staff_id = self.request.POST.get('staff_id') #System staff
        event = self.request.POST.get('event')

        if not (staff_id or event):
            return JsonResponse({
                'status':'error',
                'message':'Missing required fields.'
            })
        
        try:
            staff = User.objects.get(
                id=staff_id,
                tenant=tenant
            )
        except Exception as e:
            logger.error(f'An error occured: {e}')
            return JsonResponse({
                'status':'error',
                'message':'Invalid staff selected.'
            })
        
        try:
            TenantEventNotification.objects.create(
                tenant=tenant,
                event=event,
                staff=staff
            )
        except Exception as e:
            logger.error(f'An error occured creating a TenantEventNotification object: {e}')
            return JsonResponse({
                'status':'error',
                'message':'Unable to create an event mapping, please try again.'
            })
        
        return JsonResponse({
            'status':'success',
            'message':'Event mapped successfully.'
        })

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant

        events = TenantEventNotification.choice
        all_staffs = User.objects.filter(
            tenant=tenant
        ).exclude(
            groups__name='Member'
        )
        context['events'] = events
        context['all_staffs'] = all_staffs

        return context


# Delete Event Mapping
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Super User']), name='dispatch')
class DeleteEventNotificationMapping(DeleteView):
    model = TenantEventNotification

    def get_queryset(self):
        tenant = self.request.tenant
        return super().get_queryset().filter(
            tenant=tenant
        )
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object:
            return JsonResponse({
                'status':'error',
                'message':'Mapping not found.'
            })
        
        try:
            self.object.delete()
            return JsonResponse({
                'status':'success',
                'message':'Mapping deleted.'
            })
        except Exception as e:
            logger.error(f'{str(e)}')
            return JsonResponse({
                'status':'error',
                'message':f'Could not delete mapping.'
            })




class SchemesBrowseView(TemplateView):
    template_name = 'dashboard/schemes_browse.html'

    def get(self, request, *args, **kwargs):
        tenant_id = self.kwargs.get('tenant_id')
        request.tenant = request.tenant

        schemes = InvestmentScheme.objects.filter(tenant=request.tenant)

        search_query = request.GET.get('search', '').strip()
        if search_query:
            schemes = schemes.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query)
            )

        # status = request.GET.get('status', '')
        # if status:
        #     schemes = schemes.filter(status=status)

        schemes = schemes.annotate(
            member_count=Count('membership', distinct=True),
            total_contribution=Sum('contribution__total_contribution')
)
        schemes = schemes.order_by('name')

        export_format = request.GET.get('export')
        if export_format == 'csv':
            return export_schemes_csv(schemes)
        elif export_format == 'xlsx':
            return export_schemes_excel(schemes)
        # elif export_format == 'pdf':
        #     return export_schemes_pdf(schemes)

        paginator = Paginator(schemes, 12)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        scheme_types = InvestmentScheme.objects.filter(tenant=request.tenant).values_list('name', flat=True).distinct()

        context = {
            'page_obj': page_obj,
            'schemes': page_obj.object_list,
            'total_schemes': schemes.count(),
            'scheme_types': scheme_types,
        }
        return self.render_to_response(context)

def export_schemes_csv(schemes):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="schemes_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['Scheme Name', 'Description', 'Member Count', 'Created Date', 'Last Updated'])
    for scheme in schemes:
        writer.writerow([
            scheme.name,
            scheme.description,
            scheme.member_count,
            scheme.created_date.strftime('%Y-%m-%d'),
            scheme.updated_date.strftime('%Y-%m-%d')
        ])
    return response

def export_schemes_excel(schemes):
    data = [
        {
            'Scheme Name': scheme.name,
            'Description': scheme.description,
            'Member Count': scheme.member_count,
            'Created Date': scheme.created_at.strftime('%Y-%m-%d'),
            'Last Updated': scheme.updated_at.strftime('%Y-%m-%d'),
        } for scheme in schemes
    ]
    df = pd.DataFrame(data)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="schemes_export.xlsx"'
    df.to_excel(response, index=False)
    return response



class SchemeSettingsView(TemplateView):
    template_name = 'dashboard/configure_settings.html'

    def get(self, request, *args, **kwargs):
        tenant_id = self.kwargs.get('tenant_id')
        request.tenant = request.tenant

        schemes = InvestmentScheme.objects.filter(tenant=request.tenant)

        search_query = request.GET.get('search', '').strip()
        if search_query:
            schemes = schemes.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query)
            )

        # status = request.GET.get('status', '')
        # if status:
        #     schemes = schemes.filter(status=status)

        schemes = schemes.annotate(
            member_count=Count('membership', distinct=True),
            total_contribution=Sum('contribution__total_contribution')
)
        schemes = schemes.order_by('name')

        export_format = request.GET.get('export')
        if export_format == 'csv':
            return export_schemes_csv(schemes)
        elif export_format == 'xlsx':
            return export_schemes_excel(schemes)
        # elif export_format == 'pdf':
        #     return export_schemes_pdf(schemes)

        paginator = Paginator(schemes, 12)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        scheme_types = InvestmentScheme.objects.filter(tenant=request.tenant).values_list('name', flat=True).distinct()

        context = {
            'page_obj': page_obj,
            'schemes': page_obj.object_list,
            'total_schemes': schemes.count(),
            'scheme_types': scheme_types,
        }
        return self.render_to_response(context)

def export_schemes_csv(schemes):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="schemes_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['Scheme Name', 'Description', 'Member Count', 'Created Date', 'Last Updated'])
    for scheme in schemes:
        writer.writerow([
            scheme.name,
            scheme.description,
            scheme.member_count,
            scheme.created_date.strftime('%Y-%m-%d'),
            scheme.updated_date.strftime('%Y-%m-%d')
        ])
    return response

def export_schemes_excel(schemes):
    data = [
        {
            'Scheme Name': scheme.name,
            'Description': scheme.description,
            'Member Count': scheme.member_count,
            'Created Date': scheme.created_at.strftime('%Y-%m-%d'),
            'Last Updated': scheme.updated_at.strftime('%Y-%m-%d'),
        } for scheme in schemes
    ]
    df = pd.DataFrame(data)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="schemes_export.xlsx"'
    df.to_excel(response, index=False)
    return response