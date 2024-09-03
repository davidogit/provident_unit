from django.db.models import Q
from django.db.models.query import QuerySet
from django.http import JsonResponse
from django.http.response import HttpResponse as HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView, ListView,DetailView,UpdateView,CreateView,DeleteView,View
# Create your views here.
from Fund.models import InvestmentDetail,DelayedInterest,BankInterest
from MultiScheme.models import InvestmentScheme,Tenant
from MultiScheme.models import InvestmentScheme,Tenant
from contributions.models import StaffAPI
from django.urls import reverse, reverse_lazy
from django.core.paginator import Paginator
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from Admin.decorators import role_required
from .forms import InvestmentUpdateForm,InvestmentApprovalForm

# Importing custom decorators
from Member.decorators import tenant_required
from Member.models import SchemeApproval

class LandingPage(TemplateView):
    template_name = 'dashboard/landing_page.html'


class AccessDenied(TemplateView):
    template_name = 'dashboard/access_denied.html'

    def get(self, request, *args, **kwargs):
        # clear session data
        request.session.flush()

        return super().get(request, *args, **kwargs)

# the name=dispatch means the decorators will work for POST,GET,PUT etc
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Manager','Treasury User','HR']), name='dispatch')
class Invest(TemplateView):
    template_name='dashboard/finance.html'

    def get_context_data(self, **kwargs):
        
        # Get Tenant
        tenant_id = self.request.tenant.id
        tenant = Tenant.objects.get(id=tenant_id)

        # Get scheme name
        # scheme_name = self.request.scheme_name
        # scheme = InvestmentScheme.objects.get(id=scheme_name)

        context = super().get_context_data(**kwargs)
        # Queryset to calculate total interest Actual and Estimated

        # Estimated
        try: 
            interest_query = InvestmentDetail.objects.all().filter(~Q(_status = 'Active'), investment_scheme__tenant = tenant)
        except:
            interest_query = []
        
        context['total_interest'] = sum(inv.interest_amount for inv in interest_query)

        # Actual
        try: 
            actual_revenue = InvestmentDetail.objects.all().filter(approval_status=True,_status = 'Expired', investment_scheme__tenant = tenant)
        except:
            actual_revenue = []

        context['actual_revenue'] = sum(inv.interest_amount for inv in actual_revenue)


        # Queryset to calsulate total number of active investments
        try:
            active_inv = InvestmentDetail.objects.all().filter(_status = 'Active', investment_scheme__tenant = tenant)
            context['active_inv'] = active_inv.count()
        except:
            active_inv = []
        
        # Get schemes
        try:
            scheme = InvestmentScheme.objects.filter(tenant = tenant)
            context['schemes'] = scheme
        except:
            scheme = []

           
        

        # Queryset to calsulate total number of Active Members
        active_members = StaffAPI.objects.filter(investment_scheme__tenant=tenant)
        context['active_members'] = active_members.count()

        return context





# Creating List View for model
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury User','Manager']), name='dispatch')
class InvestmentListView(ListView):
    context_object_name = 'investment_list'
    model = InvestmentDetail
    template_name = 'dashboard/investment_list.html'


    # We override the get_queryset method to be able to filter the objects before its being accesed in this view
    def get_queryset(self):
         
        # Get Tenant
        tenant_id = self.request.tenant.id
        tenant = Tenant.objects.get(id=tenant_id)

        # Get scheme name
        scheme_name = self.request.scheme_name
        scheme = InvestmentScheme.objects.get(id=scheme_name)

        # Filtering Queryset by Tenant
        if tenant:
            return InvestmentDetail.objects.filter(investment_scheme__tenant=tenant,investment_scheme = scheme).order_by('-created_date')
        else:
            return InvestmentDetail.objects.none()
        

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        # Grouping Investment based on Types
        context['inv_type_t_bill'] = queryset.filter(investment_type='Treasury Bill')
        context['inv_type_f_dep'] = queryset.filter(investment_type='Fixed Deposit')
        # context['inv_type_d_int'] = queryset.filter(investment_type='D-interest')

        # Getting queryset for each investment type
        t_bill_queryset = queryset.filter(investment_type='Treasury Bill')
        f_deposit_queryset = queryset.filter(investment_type='Fixed Deposit')
        # d_interest_queryset = queryset.filter(investment_type='D-interest')

        # Paginating for each Tab-Pane
        t_bill_page = self.request.GET.get('t_bill_page',1)
        f_deposit_page = self.request.GET.get('f_deposit_page',1)
        # d_interest_page = self.request.GET.get('d_interest_page',1)


        # Returning context keys for each page and applying pagination
        context['t_bill_page'] = Paginator(t_bill_queryset, per_page=2).get_page(t_bill_page)
        context['f_deposit_page'] = Paginator(f_deposit_queryset,2).get_page(f_deposit_page)
        # context['d_interest_page'] = Paginator(d_interest_queryset,10).get_page(d_interest_page)


        # Counting Number of individual Investments
        context['investment_count']= queryset.count()
        context['T_bills_count'] = queryset.filter(investment_type='Treasury Bill').count()
        context['F_deposit_count'] = queryset.filter(investment_type='Fixed Deposit').count()
        # context['D_interest_count'] = queryset.filter(investment_type='D-interest').count()
        
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
        tenant_id = self.request.tenant.id
        tenant = Tenant.objects.get(id=tenant_id)

        # Get scheme name
        scheme_id = self.request.scheme_name
        scheme = InvestmentScheme.objects.get(id=scheme_id)

        # Filtering Queryset by Tenant
        if tenant:
            return InvestmentDetail.objects.filter(investment_scheme__tenant=tenant,investment_scheme = scheme)
        else:
            return InvestmentDetail.objects.none()



# Adding an investment
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury User']), name='dispatch')
class AddInvestment(CreateView):
    model=InvestmentDetail
    fields = ('investment_type','account_name','account_type','account_number','principal_amount','interest_start_date','interest_end_date','interest_percentage')
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

        scheme = get_object_or_404(InvestmentScheme.objects.filter(id=scheme_name, tenant=tenant))

        if scheme:
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
    # fields = ('investment_type','account_name','account_type','account_number','principal_amount','interest_start_date','interest_end_date','interest_percentage')
    form_class = InvestmentUpdateForm
    template_name = 'dashboard/investment_update_form.html'

    # We override the get_queryset method to be able to filter the objects before its being accesed in this view
    def get_queryset(self):
         
        # Get Tenant
        tenant_id = self.request.tenant.id
        tenant = Tenant.objects.get(id=tenant_id)

        # Get scheme name
        scheme_name = self.request.scheme_name
        scheme = InvestmentScheme.objects.get(id=scheme_name)

        # Filtering Queryset by Tenant
        if tenant:
            return InvestmentDetail.objects.filter(investment_scheme__tenant=tenant,investment_scheme = scheme)
        else:
            return InvestmentDetail.objects.none()
    
    # Make sure we are updating details under the right tenant
    def form_valid(self, form):

        tenant = self.request.tenant
        scheme_id = self.request.scheme_name

        scheme = get_object_or_404(InvestmentScheme.objects.filter(tenant=tenant, id=scheme_id))

        if scheme:
            form.instance.investment_scheme = scheme

        return super().form_valid(form)
    
    # Form instance
    def get_context_data(self, **kwargs):
        context= super().get_context_data(**kwargs)

        tenant = self.request.tenant
        scheme_id = self.request.scheme_name

        inv = InvestmentDetail.objects.filter(investment_scheme__tenant=tenant, investment_scheme__id = scheme_id).first()
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
class RolloverPercentage(UpdateView):
    model = InvestmentDetail
    fields =('rollover_interest_percentage',)
    context_object_name = 'rollover'
    template_name = 'dashboard/rollover_percentage.html'

    # We override the get_queryset method to be able to filter the objects before its being accesed in this view
    def get_queryset(self):
         
        # Get Tenant
        tenant_id = self.request.tenant.id
        tenant = Tenant.objects.get(id=tenant_id)

        # Get scheme name
        scheme_name = self.request.scheme_name
        scheme = InvestmentScheme.objects.get(id=scheme_name)

        # Filtering Queryset by Tenant
        if tenant:
            return InvestmentDetail.objects.filter(investment_scheme__tenant=tenant,investment_scheme = scheme)
        else:
            return InvestmentDetail.objects.none()

    # Make sure we are updating details under the right tenant
    def form_valid(self, form):

        tenant = self.request.tenant
        scheme_id = self.request.scheme_name

        scheme = get_object_or_404(InvestmentScheme.objects.filter(tenant=tenant, id=scheme_id))

        if scheme:
            form.instance.investment_scheme = scheme

        return super().form_valid(form)
    
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
        tenant_id = self.request.tenant.id
        tenant = Tenant.objects.get(id=tenant_id)

        # Get scheme name
        scheme_name = self.request.scheme_name
        scheme = InvestmentScheme.objects.get(id=scheme_name)

        # Filtering Queryset by Tenant
        if tenant:
            return InvestmentDetail.objects.filter(investment_scheme__tenant=tenant,investment_scheme = scheme)
        else:
            return InvestmentDetail.objects.none()
    
    def get_success_url(self):

        scheme = self.request.scheme_name
        tenant =  self.request.tenant

        return reverse('investment_list', kwargs={'scheme_name':scheme, 'tenant_id':tenant.id}) 



# Active Members List
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['HR','Manager']), name='dispatch')
class MemberListView(ListView):
    # model = Member
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
            return StaffAPI.objects.filter(investment_scheme__tenant=tenant)
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
@method_decorator(role_required(role=['HR','Manager']), name='dispatch')
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
            return StaffAPI.objects.filter(investment_scheme__tenant=tenant, investment_scheme__id=scheme_id)
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
@method_decorator(role_required(role=['HR','Manager']), name='dispatch')
class MemberDetailView(DetailView):
    # model = Member
    model = StaffAPI
    template_name = 'dashboard/member_details.html'

    # We override the get_queryset method to be able to filter the Members before its being accesed in this view
    def get_queryset(self):
         
        # Get Tenant
        tenant = self.request.tenant

        # Filtering Queryset by Tenant
        if tenant:
            return StaffAPI.objects.filter(tenant=tenant)
        else:
            return StaffAPI.objects.none()


# Updating an member's details
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['HR']), name='dispatch')
class MemberUpdateView(UpdateView):
    # model = Member
    model = StaffAPI
    fields = ('Staffnumber','status')
    template_name = 'dashboard/member_form.html'

    # We override the get_queryset method to be able to filter the Members before its being accesed in this view
    def get_queryset(self):
         
        # Get Tenant
        tenant = self.request.tenant

        # Filtering Queryset by Tenant
        if tenant:
            return StaffAPI.objects.filter(tenant=tenant)
        else:
            return StaffAPI.objects.none()
        
    # Making sure we are updating details of a specific member related to a specific tenant   
    def form_valid(self, form):

        tenant = self.request.tenant

        if tenant:
            form.instance.tenant = tenant

        return super().form_valid(form)
    

# Deleting a member from Database
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['HR']), name='dispatch')
class MemberDeleteView(DeleteView):
    # model = Member
    model = StaffAPI
    template_name = 'dashboard/delete_member.html'
    success_url = reverse_lazy('member_list')

    # We override the get_queryset method to be able to filter the Members before its being accesed in this view
    def get_queryset(self):
         
        # Get Tenant
        tenant = self.request.tenant

        # Filtering Queryset by Tenant
        if tenant:
            return StaffAPI.objects.filter(tenant=tenant)
        else:
            return StaffAPI.objects.none()


from django.utils import timezone
from datetime import datetime

# Query For Investment View
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury User','Manager']), name='dispatch')
class InvestmentQuery(ListView):
    template_name = 'dashboard/query.html'
    model = InvestmentDetail
    paginate_by = 10
    # context_object_name = 'results'

    # We override the get_queryset method to be able to filter the objects before its being accesed in this view
    def get_queryset(self):
         
        # Get Tenant
        tenant_id = self.request.tenant.id
        tenant = Tenant.objects.get(id=tenant_id)

        # Get scheme id
        scheme_id = self.request.scheme_name
        scheme = InvestmentScheme.objects.get(id=scheme_id,tenant=tenant)

        # Filtering Queryset by Tenant
        if tenant:
            return InvestmentDetail.objects.filter(investment_scheme__tenant=tenant,investment_scheme = scheme)
        else:
            return InvestmentDetail.objects.none()

    # Using get_queryset so that we can paginate seperate queries based on filter
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        sort = self.request.GET.get('sort','')
        from_date = self.request.GET.get('from-date','')
        to_date = self.request.GET.get('to-date','')
        inv_type = self.request.GET.get('inv_type','')
        status = self.request.GET.get('status','')
    

        
        # Get current date
        # current_date = timezone.now().date()

        # convert 'date' to date format
        from_date = datetime.strptime(from_date,"%Y-%m-%d").date() if from_date else None
        to_date = datetime.strptime(to_date,"%Y-%m-%d").date() if to_date else None

        # get all investments
        # queryset = InvestmentDetail.objects.all()
        queryset = self.get_queryset()

        # A list to accumulate all related search before passing it as a context
        query=[]
        
        # If no date is specified
        if from_date == None and to_date == None:
            for inv in queryset:
                # Filters investment based on 'Expired' and investment type
                if inv.status == 'Expired' and status=='matured' and (inv.investment_type==inv_type):
                    query.append(inv)

                # Filters investment based on 'Active' and investment type
                elif inv.status == 'Active' and status=='active' and (inv.investment_type==inv_type):
                    query.append(inv)

                # Filters investment based on 'Not start' and investment type
                elif inv.status == 'Not Start' and status =='Not started' and (inv.investment_type==inv_type):
                    query.append(inv)

                                
            # Returns the list of results 
            context['results'] = query

        # If dates are specified
        elif (from_date and to_date) or (inv_type or status):
            for inv in queryset:

                if sort == 'start_date':
                    search_criteria = inv.interest_start_date
                elif sort == 'created_date':
                    search_criteria = inv.created_date
                else:
                    search_criteria = inv.interest_start_date
                    
                # print(sort)
                # print(search_criteria)
                if from_date <= search_criteria <= to_date:
                # queries matured investments within the given dates
                    if inv.status == 'Expired' and status=='matured' and (inv.investment_type==inv_type):
                        query.append(inv)

                    elif inv.status == 'Active' and status=='active' and (inv.investment_type==inv_type):
                        query.append(inv)

                    elif inv.status == 'Not Start' and status =='Not started' and (inv.investment_type==inv_type):
                        query.append(inv)


            # Returns the list of results
            context['results'] = query

        return context


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
        tenant_id = self.request.tenant.id
        tenant = Tenant.objects.get(id=tenant_id)

        # Get scheme name
        scheme_name = self.request.scheme_name
        scheme = InvestmentScheme.objects.get(id=scheme_name,tenant=tenant)

        # Filtering Queryset by Tenant
        if tenant:
            return DelayedInterest.objects.filter(investment_scheme__tenant=tenant,investment_scheme = scheme)
        else:
            return DelayedInterest.objects.none()


@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury User']), name='dispatch')
class DelayedInterestCreateView(CreateView):
    template_name = 'dashboard/delayed_interest_form.html'
    model = DelayedInterest
    fields = ('from_date','to_date','amount','remarks')

    # Make sure we are updating details under the right tenant
    def form_valid(self, form):

        tenant = self.request.tenant
        scheme_id = self.request.scheme_name

        scheme = get_object_or_404(InvestmentScheme.objects.filter(tenant=tenant, id=scheme_id))

        if scheme:
            form.instance.investment_scheme = scheme

        return super().form_valid(form)
    

    def get_success_url(self):

        scheme = self.request.scheme_name
        tenant = self.request.tenant
        return reverse('delayed_interest_list', kwargs={'scheme_name':scheme, 'tenant_id':tenant.id})





@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury User','Manager']), name='dispatch')
class BankInterestListView(ListView):
    template_name = 'dashboard/bank_interest_list.html'
    model = BankInterest
    paginate_by = 10
    context_object_name = 'bank_interest'


    # We override the get_queryset method to be able to filter the objects before its being accesed in this view
    def get_queryset(self):
         
        # Get Tenant
        tenant_id = self.request.tenant.id
        tenant = Tenant.objects.get(id=tenant_id)

        # Get scheme name
        scheme_name = self.request.scheme_name
        scheme = InvestmentScheme.objects.get(id=scheme_name,tenant=tenant)

        # Filtering Queryset by Tenant
        if tenant:
            return BankInterest.objects.filter(investment_scheme__tenant=tenant,investment_scheme = scheme)
        else:
            return BankInterest.objects.none()
        




@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury User']), name='dispatch')
class BankInterestCreateView(CreateView):
    template_name = 'dashboard/bank_interest_form.html'
    model = BankInterest
    fields = ('bank_name','from_date','to_date','amount','remarks','branch','account_number')

    # Make sure we are updating details under the right tenant
    def form_valid(self, form):

        tenant = self.request.tenant
        scheme_id = self.request.scheme_name

        scheme = get_object_or_404(InvestmentScheme.objects.filter(tenant=tenant, id=scheme_id))

        if scheme:
            form.instance.investment_scheme = scheme

        return super().form_valid(form)
    

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get tenant
        tenant = self.request.tenant

        if tenant:
            context['banks'] = BankInterest.names
        else:
            context['banks'] = []

        return context
    
    def get_success_url(self):

        scheme = self.request.scheme_name
        tenant = self.request.tenant
        return reverse('bank_interest_list', kwargs={'scheme_name':scheme, 'tenant_id':tenant.id})




# Bank Interest Query
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Treasury User','Manager']), name='dispatch')
class BankInterestQuery(ListView):
    model = BankInterest
    template_name = 'dashboard/bank_interest_query.html'
    paginate_by = 20



    # We override the get_queryset method to be able to filter the objects before its being accesed in this view
    def get_queryset(self):
         
        # Get Tenant
        tenant_id = self.request.tenant.id
        tenant = Tenant.objects.get(id=tenant_id)

        # Get scheme name
        scheme_name = self.request.scheme_name
        scheme = InvestmentScheme.objects.get(id=scheme_name,tenant=tenant)

        # Filtering Queryset by Tenant
        if tenant:
            return BankInterest.objects.filter(investment_scheme__tenant=tenant,investment_scheme = scheme).order_by('-created_date')
        else:
            return BankInterest.objects.none()
        


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get tenant
        tenant = self.request.tenant

        if tenant:
            context['banks'] = BankInterest.names
        else:
            context['banks'] = []

        from_date = self.request.GET.get('from-date')
        to_date = self.request.GET.get('to-date')
        bank = self.request.GET.get('bank_name')

        # convert 'date' to date format
        from_date = datetime.strptime(from_date,"%Y-%m-%d").date() if from_date else None

        to_date = datetime.strptime(to_date,"%Y-%m-%d").date() if to_date else None

        # get all bank interest data
        queryset = self.get_queryset()

        query =[]
        if from_date and to_date:
            # Lookup all bank interest within a specified period
            for interest in queryset:
                if bank == 'all':
                    if from_date <= (interest.from_date and interest.to_date) <= to_date:
                        query.append(interest)

                    # Returns an empty list
                    # else:
                    #     query.append('')
                elif interest.bank_name == bank:
                    if from_date <= (interest.from_date and interest.to_date) <= to_date:
                        query.append(interest)
                
            context['results'] = query

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
        tenant_id = self.request.tenant.id
        tenant = Tenant.objects.get(id=tenant_id)

        # Get scheme name
        scheme_name = self.request.scheme_name
        scheme = InvestmentScheme.objects.get(id=scheme_name,tenant=tenant)

        # Filtering Queryset by Tenant
        if tenant:
            return DelayedInterest.objects.filter(investment_scheme__tenant=tenant,investment_scheme = scheme).order_by('-created_date')
        else:
            return DelayedInterest.objects.none()
        

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get search elements from user

        from_date = self.request.GET.get('from-date')
        to_date = self.request.GET.get('to-date')

        # convert 'date' to date format
        from_date = datetime.strptime(from_date,"%Y-%m-%d").date() if from_date else None

        to_date = datetime.strptime(to_date,"%Y-%m-%d").date() if to_date else None

        # Fetch all Delayed Interest
        queryset = self.get_queryset()

        # List to append related search results
        query = []
        if from_date and to_date:
            for d_interest in queryset:
                if from_date <= d_interest.from_date and d_interest.to_date <= to_date:
                    query.append(d_interest)

            context['results'] = query

        else:
            context['results'] = query
        return context
    


# Approval of investments
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

        # Check if 'investment_id' is provided
        if not inv_id:
            return JsonResponse({'status': 'error', 'message': 'Investment ID is required.'}, status=400)

        if form.is_valid():
            investment = get_object_or_404(InvestmentDetail,id=inv_id,investment_scheme__tenant=tenant, investment_scheme__id=scheme_id,approval_status=False, _status='Expired')

            closing_amount = form.cleaned_data.get('closing_amount')
            approval_status = form.cleaned_data.get('approval_status')

            # Validate that 'closing_amount' and 'approval_status' are provided
            if closing_amount is None or approval_status is None:
                return JsonResponse({'status': 'error', 'message': 'Closing amount and approval status are required.'}, status=400)

            # Check if closing amount == expected amount
            if investment.interest_amount==closing_amount:
                # Alter fields of approval
                investment.approval_status = approval_status
                investment.closing_amount = closing_amount
                investment.save()

                return JsonResponse({'status':'success'})
            else:
                # Gather the error message
                error_message = 'Closing amount does not match with expected amount'
                return JsonResponse({'status':'error', 'message':error_message}, status=400)

        return JsonResponse({'status':'error'}, status=400)


    def get_context_data(self, **kwargs):
        context=super().get_context_data(**kwargs)

        context['approval_form']=InvestmentApprovalForm()
        return context


# Approved Investments list

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



# LIST OF APPROVALS
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
        return super().get_queryset()
    
    
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
            application = SchemeApproval.objects.get(tenant=tenant, id=application_id)
            # Now we can approve useing the approve method on the SchemeApproval Model
            application.approve()
            return JsonResponse({'status':'success', 'approved_by_hr':approved_by_hr})
        except SchemeApproval.DoesNotExist:
            return JsonResponse({'status':'error'},status=400)
