from decimal import Decimal
from django.db.models import Q,Count
from django.db.models.query import QuerySet
from django.http import HttpRequest, JsonResponse
from django.http.response import HttpResponse as HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView, ListView,DetailView,UpdateView,CreateView,DeleteView,View
from ProvidentFund.settings import EMAIL_HOST_USER
from Fund.models import InvestmentDetail,DelayedInterest,BankInterest,BankInterestRate
from Member.models import Member
from MultiScheme.models import InvestmentScheme,Tenant,SchemeSettings
from MultiScheme.models import InvestmentScheme,Tenant
from contributions.models import StaffAPI, Contribution
from django.urls import reverse, reverse_lazy
from django.core.paginator import Paginator
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from Admin.decorators import role_required
from .forms import InvestmentUpdateForm,InvestmentApprovalForm
from Fund.tasks import actual_member_interest,rollover_inv_creation
from Member.tasks import gen_send_email
from django.core.exceptions import ValidationError
from django.db.models import Sum,F
import logging
from django.utils import timezone
from datetime import datetime, timedelta
from django.utils.dateparse import parse_date
from urllib.parse import urlencode
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.core.exceptions import ObjectDoesNotExist
from Chart_of_Accounts.models import ChartOfAccounts,AccountMapping
from Fund.tasks import calculate_staff_contribution

logger = logging.getLogger(__name__)

# Importing custom decorators
from Member.decorators import tenant_required,tenant_login_required
from Member.models import SchemeApproval

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
        request.session.flush()

        return super().get(request, *args, **kwargs)

# the name=dispatch means the decorators will work for POST,GET,PUT etc
@method_decorator(login_required, name='dispatch') 
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Manager', 'Treasury User', 'HR','Finance Manager']), name='dispatch')
class Invest(TemplateView):
    template_name = 'dashboard/finance.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get Tenant
        tenant = Tenant.objects.prefetch_related('staff_api').get(id=self.request.tenant.id)
        # Fetch schemes and related investments using prefetch
        schemes = InvestmentScheme.objects.filter(tenant=tenant).prefetch_related('member')
        try:
            interest_query = InvestmentDetail.objects.filter(investment_scheme__tenant=tenant)
        except:
            interest_query.none()
        # Total Interest - Estimated and Actual
        try:
            estimated_amount = interest_query.filter(approval_status=False).aggregate(total = Sum('interest_amount'))['total'] or 0.0
            
            context['total_interest'] = estimated_amount
        except:
            context['total_interest'] = 0.0

        try: 
            actual_revenue = interest_query.filter(approval_status=True, _status='Expired').aggregate(total = Sum('interest_amount'))['total'] or 0.0

            context['actual_revenue'] =  actual_revenue
        except:
            context['actual_revenue'] = 0.0

        # Active Investments
        try:
            context['active_inv'] = interest_query.count()
        except:
            context['active_inv'] = 0

        # Active Members
    
        context['active_members'] = tenant.staff_api.count()

        # Bank Interest Rates
        try:
            context['interest_rates'] = BankInterestRate.objects.all()
        except:
            context['interest_rates'] = []

        # Available Investment Schemes
        try:
            context['investment_scheme'] = schemes
        except:
            context['investment_scheme'] = []

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

        context['gender_counts_by_scheme'] = gender_counts_by_scheme
        return context


# Creating List View for model
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury User','Manager']), name='dispatch')
class InvestmentListView(ListView):
    context_object_name = 'investment_list'
    model = InvestmentDetail
    template_name = 'dashboard/investment_list.html'
    paginate_by = 10


    # We override the get_queryset method to be able to filter the objects before its being accesed in this view
    def get_queryset(self):
        # Get Tenant
        tenant = self.request.tenant
        # Get scheme name
        scheme_id = self.request.scheme_name

        # Filtering Queryset by Tenant
        if tenant:
            return InvestmentDetail.objects.filter(investment_scheme__tenant=tenant,investment_scheme__id = scheme_id).order_by('-created_date')
        else:
            return InvestmentDetail.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        # pass queryset to custom function for further filtering
        # filtered_queryset = self.get_filtered_queryset(queryset)

        context['investment_count']= queryset.count()
        context['T_bills_count'] = queryset.filter(investment_type='Treasury Bill').count()
        context['F_deposit_count'] = queryset.filter(investment_type='Fixed Deposit').count()


        # context['t_bill_page'] 

        fixed_deposit =queryset.filter(investment_type='Fixed Deposit')
        paginator = Paginator(fixed_deposit, self.paginate_by)
        page = self.request.GET.get('f_deposit_page',1)
        try:
            paginated_queryset = paginator.page(page)

        except PageNotAnInteger:
            paginated_queryset = paginator.page(1)
        except EmptyPage:
            paginated_queryset = paginator.page(paginator.num_pages)

        context['f_deposit_page'] = paginated_queryset
        context['paginator'] = paginator
        context['fixed_is_paginated'] = paginator.num_pages > 1
        print(f'Paginated F: {paginated_queryset} is paginated:{paginator.num_pages > 1} has next: {paginated_queryset.has_next()}')
        # Add paginated results to context
            

        treasury_bills = queryset.filter(investment_type='Treasury Bill')
        # Apply pagination for Tresury bill or Fixed deposit

        # print(f'Filtered T_bill = {filtered_queryset}')
        paginator = Paginator(treasury_bills, self.paginate_by)
        page = self.request.GET.get('t_bill_page')
        try:
            paginated_queryset = paginator.page(page)
        except PageNotAnInteger:
            paginated_queryset = paginator.page(1)
        except EmptyPage:
            paginated_queryset = paginator.page(paginator.num_pages)

        # Add paginated results to context
        context['t_bill_page'] = paginated_queryset
        context['paginator'] = paginator
        context['is_paginated'] = paginator.num_pages > 1

        return context
    

# Investment Detail View
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury User','Manager']), name='dispatch')
class InvestmentDetailView(DetailView):
    model = InvestmentDetail
    template_name = 'dashboard/investment_details.html'
    context_object_name = 'investment_detail'

    # We override the get_queryset method to be able to filter the objects before its being accesed in this view
    def get_queryset(self):
         
        # Get Tenant
        tenant = self.request.tenant        

        # Get scheme name
        scheme_id = self.request.scheme_name

        # Filtering Queryset by Tenant
        if tenant:
            return InvestmentDetail.objects.filter(investment_scheme__tenant=tenant,investment_scheme__id = scheme_id)
        else:
            return InvestmentDetail.objects.none()

    def post(self, request, *args, **kwargs):
        if request.method == 'POST':
            try:
                print('START')
                tenant = request.tenant
                scheme_id = request.scheme_name
                inv_id = request.POST.get('inv_id')
                termination_date_str = request.POST.get('termination_date')
                termination_interest_str = request.POST.get('termination_interest')
                termination_interest = Decimal(termination_interest_str)

                try:
                    scheme = InvestmentScheme.objects.filter(
                        tenant=tenant,
                        id = scheme_id
                    ).prefetch_related('account_mapping').first()
                except Exception:
                    return JsonResponse({
                        'status':'error',
                        'message':'Investment scheme not found.'
                    })
                
                try:
                    mapping = scheme.account_mapping.get(name='Redeem Investment')
                except Exception:
                    return JsonResponse({
                        'status':'error',
                        'message':'No account mapping for "Redeem Investment" found. Please create a mapping for this event and try again.'
                    })
                
                # fetch debit and credit accounts
                debit_account = mapping.debit_acc
                credit_account = mapping.credit_acc

                if not debit_account or not credit_account:
                    return JsonResponse({
                        'status':'error',
                        'message':'Debit or Credit accounts not properly configured'
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
                        investment_scheme__tenant=tenant,
                        investment_scheme__id=scheme_id
                    )

                except InvestmentDetail.DoesNotExist:
                    return JsonResponse({'status': 'error', 'message': "Couldn\'t find investment object"})

                current_date = timezone.now().date()
                if current_date>inv.interest_end_date:
                    return JsonResponse({
                        'status':'error',
                        'message':'This investment is matured hence can\'t be terminated.'
                    })

                # Calculate interest up to termination date
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
                    debit_account.current_balance -= termination_interest
                    credit_account.current_balance += termination_interest

                    # Save debit and credit operaions
                    debit_account.save()
                    credit_account.save()
                
                return JsonResponse({'status': 'success', 'message': 'Investment terminated successfully.'})
            except InvestmentDetail.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Investment not found.'})
            except Exception as e:
                return JsonResponse({'status': f'error', 'message': 'An unexpected error occurred.: {e}'})


# Adding an investment
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury User']), name='dispatch')
class AddInvestment(CreateView):
    model=InvestmentDetail
    fields = ('investment_type','account_name','account_type','account_number','principal_amount','interest_start_date','interest_end_date','interest_percentage','years','componding_frequency','type_of_tbill')
    template_name = 'dashboard/investment_form.html'
    # success_url = reverse_lazy('investment_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get tenant from request
        tenant = self.request.tenant

        if tenant:
            context['account_type'] = InvestmentDetail.account
            context['inv_type'] = InvestmentDetail.inv_type
        else:
            context['account_type'] = []
            context['inv_type'] = []

        return context
    
    # Make sure we are updating details under the right tenant
    def form_valid(self, form):
        tenant = self.request.tenant
        scheme_name = self.request.scheme_name

        scheme = InvestmentScheme.objects.filter(id=scheme_name, tenant=tenant).prefetch_related('account_mapping').first()

        if not scheme:
            return JsonResponse({
                'status':'error',
                'message':'Investment scheme not found'
            })
        
        mapping = scheme.account_mapping.get(name='Investment')
        if not mapping:
            return JsonResponse({
                'status':'error',
                'message':'Mapping not found. Make sure a mapping is created for this event then try again.'
            })
        
        # Fetch investment principal
        investment_amount = form.cleaned_data['principal_amount']
        
        with transaction.atomic():
            # Fetch debit and credit accounts from mapping obj
            debit_account = mapping.debit_acc
            credit_account = mapping.credit_acc

            if not debit_account and credit_account:
                return JsonResponse({
                    'status':'error',
                    'message':'Debit and Credit accounts not properly configured'
                })
            
            # Prevent cases of insufficient balance when trying to debit an account
            if debit_account.current_balance < investment_amount:
                return JsonResponse({
                    'status':'error',
                    'message':f'Insufficient balance for {debit_account}'
                })
            
            # perform debit anf credit operations
            debit_account.current_balance -= investment_amount
            credit_account.current_balance += investment_amount

            # save account balances
            debit_account.save()
            credit_account.save()

        # set scheme on investment object
        form.instance.investment_scheme = scheme

        return super().form_valid(form)
    

    def get_success_url(self):

        scheme = self.request.scheme_name
        tenant =  self.request.tenant

        return reverse('investment_list', kwargs={'scheme_name':scheme, 'tenant_id':tenant.id}) 



# Updating an Investement's details
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury User']), name='dispatch')
class InvestmentUpdateView(UpdateView):
    model = InvestmentDetail
    form_class = InvestmentUpdateForm
    template_name = 'dashboard/investment_update_form.html'

    # We override the get_queryset method to be able to filter the objects before its being accesed in this view
    def get_queryset(self):
         
        # Get Tenant
        tenant = self.request.tenant

        # Get scheme name
        scheme_id = self.request.scheme_name

        # get inv pk
        pk = self.kwargs['pk']

        # Filtering Queryset by Tenant
        if tenant:
            return InvestmentDetail.objects.filter(pk=pk,investment_scheme__tenant=tenant,investment_scheme__id = scheme_id)
        else:
            return InvestmentDetail.objects.none()
    
    # Make sure we are updating details under the right tenant
    def form_valid(self, form):
        try:
            tenant = self.request.tenant

            scheme = self.get_queryset().first().investment_scheme

            if scheme:
                form.instance.investment_scheme = scheme
                response = super().form_valid(form)
                # form.save()
                # add success url to redirect user after a successful update
                print('form saved')
                return JsonResponse({'status':'success', 'redirect_url':self.get_success_url()})

        except ValidationError as e:
            return JsonResponse({'status':'error', 'message':str(e.message)})
        return response
    
    # Form instance
    def get_context_data(self, **kwargs):
        context= super().get_context_data(**kwargs)

        tenant = self.request.tenant
        scheme_id = self.request.scheme_name
        # get inv instance
        pk = self.kwargs['pk']

        inv = InvestmentDetail.objects.filter(pk=pk,investment_scheme__tenant=tenant, investment_scheme__id = scheme_id).first()
        
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
@method_decorator(role_required(role=['Treasury User']), name='dispatch')
class RolloverPercentage(TemplateView):
    template_name = 'dashboard/rollover_percentage.html'

    def post(self, request, *args, **kwargs):
        print(self.request.POST)
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
        scheme = InvestmentScheme.objects.filter(id=scheme_id,tenant=tenant).prefetch_related('account_mapping').first()

        if not scheme:
            return JsonResponse({
                'status':'error',
                'message':'Investment scheme not found'
            })
        
        mapping = scheme.account_mapping.get(name='Roll Over')
        if not mapping:
            return JsonResponse({
                'status':'error',
                'message':'Mapping not found. Make sure a mapping is created for this event then try again.'
            })

        # Increment rollover count of original investment
        try:
            inv = get_object_or_404(InvestmentDetail,pk=pk,investment_scheme__tenant=request.tenant,investment_scheme__id=scheme_id,approval_status=False,termination_status=False)
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
        debit_or_credit = None
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
            inv = get_object_or_404(InvestmentDetail,pk=pk,investment_scheme__tenant=tenant,investment_scheme__id = scheme_id)     
        
        context['rollover']= inv
        return context
    
    def get_success_url(self):

        scheme_id = self.request.scheme_name
        tenant =  self.request.tenant

        return reverse('investment_list', kwargs={'scheme_name':scheme_id, 'tenant_id':tenant.id})


# Deleting an Investment from Database
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury User']), name='dispatch')
class InvestmentDeleteView(DeleteView):
    model = InvestmentDetail
    context_object_name = 'investment'
    template_name = 'dashboard/delete_investment.html'

    # We override the get_queryset method to be able to filter the objects before its being accesed in this view
    def get_queryset(self):   
        # Get Tenant
        tenant = self.request.tenant
        # Get scheme name
        scheme_id = self.request.scheme_name
        # Get inv pk
        pk=self.kwargs['pk']

        # Filtering Queryset by Tenant
        if tenant:
            return InvestmentDetail.objects.filter(pk=pk,investment_scheme__tenant=tenant,investment_scheme__id = scheme_id)
        else:
            return InvestmentDetail.objects.none()
    
    def get_success_url(self):
        scheme = self.request.scheme_name
        tenant =  self.request.tenant

        return reverse('investment_list', kwargs={'scheme_name':scheme, 'tenant_id':tenant.id}) 



# Active Members List
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Manager','Finance Manager']), name='dispatch')
class MemberListView(ListView):
    model = StaffAPI
    template_name = 'dashboard/member_list.html'
    # context_object_name = 'member_list'

    # We override the get_queryset method to be able to filter the Members before its being accesed in this view
    def get_queryset(self):  
        # Get Tenant
        tenant = self.request.tenant
        scheme_id = self.request.scheme_name

        # Filtering Queryset by Tenant
        if tenant:
            return StaffAPI.objects.filter(tenant=tenant,investment_scheme__id=scheme_id)
        else:
            return StaffAPI.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset().filter(exited_flag = False)

        # Active members
        context['member_list'] = queryset

        # Count all active members
        context['member_count'] = queryset.count()

        # All member count
        context['total_members'] = self.get_queryset().count()

        return context
    



# Exited Members List
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['HR','Manager','Finance Manager']), name='dispatch')
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
@method_decorator(role_required(role=['Manager','Finance Manager']), name='dispatch')
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
@method_decorator(role_required(role=['Treasury User','Manager']), name='dispatch')
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
            return InvestmentDetail.objects.filter(investment_scheme__id=scheme_id,investment_scheme__tenant=tenant).order_by('-created_date')
        return InvestmentDetail.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

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
                if sort == 'start_date':
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
@method_decorator(role_required(role=['Treasury User','Manager']), name='dispatch')
class DelayedInterestListView(ListView):
    template_name = 'dashboard/delayed_interest_list.html'
    model = DelayedInterest
    paginate_by = 10
    context_object_name = 'delayed_interest'

    # We override the get_queryset method to be able to filter the objects before its being accesed in this view
    def get_queryset(self):
         
        # Get Tenant
        tenant = self.request.tenant
        # Get scheme name
        scheme_id = self.request.scheme_name

        # Filtering Queryset by Tenant
        if tenant:
            return DelayedInterest.objects.filter(investment_scheme__tenant=tenant,investment_scheme__id = scheme_id,approved=False).order_by('-created_date')
        else:
            return DelayedInterest.objects.none()
    
    # Post method to handle approval and debit/credit operations
    def post(self, *args, **kwargs):
        tenant = self.request.tenant
        scheme_id = self.request.scheme_name
        delayed_int_id = self.request.POST.get('d_int_id', None)

        # Log inputs for debugging
        print(f'Did: {delayed_int_id}, SchemeID: {scheme_id}')

        # Validate required fields
        fields = [tenant, scheme_id, delayed_int_id]
        if not all(fields):
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required fields'
            })

        # Fetch investment scheme
        scheme = InvestmentScheme.objects.filter(
            id=scheme_id, tenant=tenant
        ).prefetch_related('delayed_interest', 'account_mapping').first()

        if not scheme:
            return JsonResponse({
                'status': 'error',
                'message': 'Investment scheme not found.'
            })

        try:
            # Fetch account mapping
            mapping = scheme.account_mapping.get(name='Approved Delayed Interest')
        except ObjectDoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'No mapping found for "Approved Delayed Interest".'
            })

        try:
            # Fetch delayed interest object
            delayed_interest_object = scheme.delayed_interest.get(id=delayed_int_id)
        except ObjectDoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Delayed interest not found.'
            })

        with transaction.atomic():
            # Fetch debit and credit accounts
            debit_account = mapping.debit_acc
            credit_account = mapping.credit_acc

            if not (debit_account and credit_account):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Debit and Credit accounts are not properly configured.'
                })

            # Validate delayed interest amount
            delayed_interest_amount = delayed_interest_object.principal
            if delayed_interest_amount <= 0:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid delayed interest amount.'
                })

            # Perform debit and credit operations
            debit_account.current_balance -= delayed_interest_amount
            credit_account.current_balance += delayed_interest_amount

            # Save account balances
            debit_account.save()
            credit_account.save()

            # Update delayed interest status
            delayed_interest_object.approved = True
            delayed_interest_object.status = 'Paid'
            delayed_interest_object.approved_by = self.request.user
            delayed_interest_object.save()

        # Return success response
        return JsonResponse({
            'status': 'success',
            'message': 'Delayed interest approved successfully.'
        })


    
    def get_context_data(self, **kwargs):
        context=super().get_context_data(**kwargs)
        page_number = self.request.GET.get('page', 1)
        start_index = (int(page_number) - 1) * self.paginate_by + 1
        queryset = self.get_queryset()
        context['delayed_int_count'] = queryset.count()
        context['total_amount'] = queryset.all().aggregate(total=Sum('principal'))['total'] or 0.00
        context['start_index'] = start_index
        return context


# Delayed Interest Query
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury User','Manager']), name='dispatch')
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
@method_decorator(role_required(role=['Manager']), name='dispatch')
class InvestmentApproval(ListView):
    model = InvestmentDetail
    template_name = 'dashboard/investment_approval.html'

    def get_queryset(self):
        tenant = self.request.tenant
        scheme_id = self.request.scheme_name

        if tenant and scheme_id:
            # Matured investments to be approved
            return InvestmentDetail.objects.filter(investment_scheme__tenant=tenant, investment_scheme__id=scheme_id,approval_status=False, _status='Expired')
        else:
            return InvestmentDetail.objects.none()
        
    def post(self, request, *args, **kwargs):
        form = InvestmentApprovalForm(request.POST)
        inv_id = request.POST.get('investment_id')
        tenant = request.tenant
        scheme_id = request.scheme_name
        tenant_id = tenant.id

        scheme = InvestmentScheme.objects.filter(tenant=tenant,id=scheme_id).prefetch_related('account_mapping').first()

        # Check if 'investment_id' is provided
        if not inv_id:
            return JsonResponse({'status': 'error', 'message': 'Investment ID is required.'})

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
            
            try:
                mapping = scheme.account_mapping.get(name='Approved Revenue')
            except Exception as e:
                return JsonResponse({
                    'status':'error',
                    'message':f'Account mapping not found for Approved Revenue event: Please create a mapping for this event and try again.'
                })
            
            # fetch debit and credit accounts
            debit_account = mapping.debit_acc
            credit_account = mapping.credit_acc

            if not debit_account or not credit_account:
                return JsonResponse({
                    'status':'error',
                    'message':'Debit or Credit accounts not set for "Approved Revenue" mapping'
                })

            # Check if closing amount == expected amount
            with transaction.atomic():
                if investment.interest_amount==closing_amount:
                    # Alter fields of approval and save
                    investment.approval_status = approval_status
                    investment.closing_amount = closing_amount
                    investment.save()

                    # perform debit and credit operation
                    debit_account.current_balance -= investment.interest_amount
                    credit_account.current_balance += investment.interest_amount

                    # Save accounts
                    debit_account.save()
                    credit_account.save()

                    # After saving changes now we calculate members actual profit using tasks
                    actual_member_interest.delay(tenant_id,scheme_id,inv_id)

                    return JsonResponse({'status':'success','message':'Investment approved successfully and accounts updated.'})
                else:
                    # Gather the error message
                    error_message = 'Closing amount does not match with expected amount'
                    return JsonResponse({'status':'error', 'message':error_message})

        # return JsonResponse({'status':'error'}, status=400)


    def get_context_data(self, **kwargs):
        context=super().get_context_data(**kwargs)

        context['approval_form']=InvestmentApprovalForm()
        return context


# Approved Investments list
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Manager']), name='dispatch')
class ApprovedInvestments(ListView):
    model = InvestmentDetail
    template_name = 'dashboard/approved_investments.html'
    paginate_by = 10

    def get_queryset(self):

        tenant = self.request.tenant
        scheme_id = self.request.scheme_name

        if tenant and scheme_id:
            return InvestmentDetail.objects.filter(investment_scheme__tenant=tenant, investment_scheme__id=scheme_id, approval_status=True)
        else:
            return InvestmentDetail.objects.none()



# LIST OF SCHEME APPLICATION APPROVALS
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['HR','Manager']), name='dispatch')
class ToBeApproved(ListView):
    model = SchemeApproval
    template_name = 'dashboard/scheme_approval.html'
    context_object_name = 'schemeapproval_list'


    def get_queryset(self):
        tenant = self.request.tenant

        if tenant:
            try:
                # Filter where scheme hasnt been approved and tenant
                return SchemeApproval.objects.filter(tenant=tenant,approved_by_hr=False)
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

@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Manager']), name='dispatch')
class RecentActivities(ListView):
    model = InvestmentDetail
    template_name = 'dashboard/all_history.html'
    paginate_by = 2

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
@method_decorator(role_required(role=['Finance Manager']), name='dispatch')
class ApproveContributions(TemplateView):
    template_name = 'dashboard/approve_contributions.html'

    def post(self,request,*args,**kwargs):
        tenant = request.tenant
        tenant_id = tenant.id
        scheme_id = request.scheme_name
        month = request.POST.get('month')
        year = request.POST.get('year')
        message_1 = '' #holder for extra message to user

        scheme = InvestmentScheme.objects.filter(
            id=scheme_id,
            tenant=tenant).prefetch_related('account_mapping').first()
        
        if not scheme:
            return JsonResponse({
                'status':'error',
                'message':'Investment scheme not found.'
            })
        
        try:
            # Mapping for contribution
            mapping = scheme.account_mapping.get(name='Contribution')
        except Exception:
            return JsonResponse({
                'status':'error',
                'message':'No account mapping for "contributioin" found. Please create a mapping for this event and try again.'
            })
        
        try:
            # Mappingh for Delayed Interest
            delayed_int_mapping = scheme.account_mapping.get(name='Delayed Interest')
        except Exception:
            return JsonResponse({
                'status':'error',
                'message':'No account mapping for "Delayed Interest" found. Please create a mapping for this event and try again.'
            })
        
        if not month and year:
            return JsonResponse({
                'status':'error',
                'message':'Month and Year are required'
            })
        
        # collect settings related to the scheme
        settings = SchemeSettings.objects.get(
            investment_scheme=scheme,
            investment_scheme__tenant=tenant
            )

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

        if not contributions.exists():
            return JsonResponse({'status': 'error', 'message': 'No contributions found for the given month.'})
        
        # Aggregtae total_contributions
        total_contribution = contributions.aggregate(
                total=Sum('total_contribution')
                )['total'] or 0
        if total_contribution == 0:
            return JsonResponse({
                'status':'error',
                'message':'Total contributions is zero.'
            })
        
        # Approve contributions and peform debit and credit operations
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
            debit_account.current_balance -= total_contribution
            credit_account.current_balance += total_contribution

            # save account balances
            debit_account.save()
            credit_account.save()


        # update staff contributions using task
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

        # First day of month
        first_day_of_month = now.replace(day=1,month=int(month),year=int(year))

        print(first_day_of_month)
        # expected payment date
        due_date = first_day_of_month + timedelta(contribution_day)
        # due date after grace period
        grace_period_end = due_date + timedelta(grace_period)

        # check if payment is delayed past grace period
        if now > grace_period_end: #if payment date is over grace period
            
            # Calculate delayed interest principal = acrued interest on contributions until approval date after grace period

            # monthly contribution total
            month_contribution = Contribution.objects.filter(
                investment_scheme__tenant=tenant,
                investment_scheme__id=scheme_id,
                month=month,
                year=year,
                approved_contribution=True).aggregate(
                    total=Sum('total_contribution')
                    )['total'] or 0.0
            
            print(f'Monthly = {month_contribution}')

            # Calculate amount due after grace period
            duration = (now - grace_period_end).days

            print(f'Duration = {duration}')

            # convert percentage --> decimal
            daily_delayed_rate = (rate/100) 

            # Using compound interest to calculate the delayed Interest on contribution
            t = Decimal((duration/30)/12) #convert duration from days to years
            n = 365
            p = month_contribution
            r = daily_delayed_rate
            c = p*(1+(r/n))**(n*t) #compound interest asuming t=1 year
            delayed_principal = c-p

            # create delayed interest object
            DelayedInterest.objects.create(
                investment_scheme=scheme,
                remarks = f'Delayed Interest for {month} /{year}',
                rate_d_int = rate,
                period_of_interest_calculation =settings.period_of_delayed_calculation,
                principal = delayed_principal,
            )

            # After creating delayed interest perform debit and credit operations

            with transaction.atomic():
                # Fetch debit and credit accounts from mapping obj
                debit_account_delayed = delayed_int_mapping.debit_acc
                credit_account_delayed = delayed_int_mapping.credit_acc

                if not debit_account_delayed or not credit_account_delayed:
                    return JsonResponse({
                        'status':'error',
                        'message':'Debit or Credit accounts not properly configured'
                    })
                
                # perform debit anf credit operations
                debit_account_delayed.current_balance -= delayed_principal
                credit_account_delayed.current_balance += delayed_principal

                # save account balances
                debit_account_delayed.save()
                credit_account_delayed.save()


            message_1 = (
                f'This payment is overdue hence a delayed interest entry is created for '
                f'the month of {month}/{year}'
            )
        
        message = f'Successfully approved investments for {month}/{year}, and Accounts updated successfully  NB:{message_1}'
        return JsonResponse({'status':'success', 'message':message})


@method_decorator(tenant_login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
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
            from contributions.models import Contribution
            queryset = Contribution.objects.filter(investment_scheme__id=scheme_id,investment_scheme__tenant=tenant,month=month,year=year,approved_contribution=False)


            # If no contributions are found, return an appropriate response
            if not queryset.exists():
                return JsonResponse({'status': 'error', 'message': 'No contributions found for the given criteria.'})


            total_number = queryset.count()
            total_amount = queryset.aggregate(total_amount=Sum('total_contribution'))['total_amount'] or 0
            contribution_date = queryset.first().contribution_date
            contribution_status = queryset.first().approved_contribution

            # object response
            return JsonResponse({'number_of_contributions':total_number,
                'total_amount':total_amount,
                'date_of_contribution':contribution_date,
                'contribution_status':contribution_status,
                'status':'success'})
        except Exception as e:
            return JsonResponse({'status':'error', 'message':str(e)})

from Member.models import ExitApproval
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['HR',]), name='dispatch')
class ApproveExitedMembers(TemplateView):
    # model = ExitApproval
    template_name = 'dashboard/exiting_members.html'
    # context_object_name = 'exiting_members'

    def post(self,request,*args,**kwargs):
        if request.method == 'POST':
            tenant = request.tenant
            application_id = request.POST.get('application_id')
            approved = request.POST.get('approved')
            member_id = request.POST.get('member_id')
            staff_id = request.POST.get('staff_id')
            scheme_id = request.POST.get('scheme_id')
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
                        scheme_to_remove = get_object_or_404(InvestmentScheme, tenant=tenant,id=scheme_id)

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


# Create an Exception to be called when theres Missing IDs in member scheme ID list when uploading members
class MissingSchemeIdError(Exception):
    def __init__(self, missing_ids, message = 'Scheme with ID(s) ', *args):
        self.missing_ids = missing_ids
        self.message = f'{message}: {missing_ids}'
        super().__init__(self.message)

# MASS MEMBER UPLOAD
import openpyxl
from django.db import transaction
class MassMemberUpload(CreateView ):
    model= StaffAPI
    fields =('__all__')
    template_name = 'dashboard/mass_enroll.html'
    
    def post(self, request, *args, **kwargs):
        print('There was a post request to this view')
        if request.FILES["excel_sheet"]:
            tenant = request.tenant
            excel_file = request.FILES["excel_sheet"]
            # Try creating users
            try:
                # Secutity check on file before processing
                try:
                    wb = openpyxl.load_workbook(excel_file,read_only=True,data_only=True) #load file
                    sheet = wb.active #read file
                except Exception:
                    return JsonResponse({
                        'status':'error',
                        'message':'Unsuported File Format'
                    })

                # scheme list
                member_scheme_ids = []
                # Members list
                all_members=[]
                # Accumulate error messages when assigning schemes
                error_message = ''

                for row in sheet.iter_rows(min_row=2,values_only=True):
                    if all(cell in (None,'') for cell in row):
                        continue #skip empty rows
                    else:   
                        try:
                            # Get data from rows --> fields
                            staff_number,first_name,last_name,scheme_id,_amount,actual_amount,subscription_date = row
                            # Convert scheme ids to a list
                            if isinstance(scheme_id,str):
                                scheme_id = scheme_id.split(',')
                            elif isinstance(scheme_id,int):
                                scheme_id = [scheme_id]
                            else:
                                return JsonResponse({
                                    'status':'error',
                                    'message':f'Invalid data type for scheme id for staff: {staff_number}'
                                })

                            # create member instance
                            member_instance = StaffAPI(
                                tenant=tenant,
                                staff_number=staff_number,
                                first_name= first_name,
                                last_name=last_name,
                                _amount=_amount,
                                actual_amount=actual_amount,
                                subscription_date=subscription_date
                            )
                            # Add member to list
                            all_members.append(member_instance)
                            # Get all scheme id's
                            member_scheme_ids.append(scheme_id if scheme_id else []) #split scheme ids

                        except Exception as e:
                            return JsonResponse({
                                'status':'error',
                                'message':f'Error processing rows{row}: {str(e)}\n'
                            })
                try:
                    with transaction.atomic():
                        # Save members without schemes
                        created_members = StaffAPI.objects.bulk_create(all_members)

                        # Refresh created_members after bulk create to assign pks to them
                        created_members = StaffAPI.objects.filter(staff_number__in=[member.staff_number for member in all_members])

                        # Now set schemes on all members
                        for member,scheme_id in zip(created_members,member_scheme_ids):
                            # Fetch related schemes
                            try:
                                # Fetch related schemes
                                schemes = InvestmentScheme.objects.filter(tenant=tenant, id__in=scheme_id)

                                # Assign scheme to member
                                member.investment_scheme.add(*schemes) #use list upacking to pass objects one by one

                                # Catch missing schemes in scheme_id provided
                                if len(scheme_id) != len(schemes):
                                    missing_ids = set(scheme_id)- set(schemes.values_list('id', flat=True))
                                    print(missing_ids)
                                    raise MissingSchemeIdError(missing_ids) #raise custom error
                            except MissingSchemeIdError as e:
                                error_message += f'{e.message} not found for: {member.last_name} {member.first_name} || \n'
                                continue
                            except Exception as e:
                                print(e)
                                error_message += f'{e} for: {member.last_name} {member.first_name} || \n'
                except Exception as e:
                    return JsonResponse({
                        'status':'error',
                        'message':f'An error occured: {e}'
                    })
                
                return JsonResponse({
                    'status':'success',
                    'message': f'Members uploaded successfully\n {"" if error_message=="Invalid scheme ID for: " else error_message}'
                })
            
            except Exception as e:
                return JsonResponse({
                    'status':'error',
                    'message':f'An error occured: {str(e)}'
                })
            
        else:
            return JsonResponse({
                'status':'error',
                'message':'Couldnt Find File'
            })


# General Payout View
class GeneralPayoutView(TemplateView):
    template_name = 'dashboard/general_payout.html'
    