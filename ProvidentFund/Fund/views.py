from django.views.generic import TemplateView, ListView,DetailView,UpdateView,CreateView,DeleteView
# Create your views here.
from Fund.models import InvestmentDetail,DelayedInterest,BankInterest
from contributions.models import StaffAPI
from django.urls import reverse_lazy
from django.core.paginator import Paginator
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required

@method_decorator(login_required, name='dispatch')
class Invest(TemplateView):
    template_name='dashboard/finance.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Queryset to calculate total interest
        interest_query = InvestmentDetail.objects.all().filter(_status = 'Active')
        context['total_interest'] = sum(inv.interest_amount for inv in interest_query)

        # Queryset to calsulate total number of active investments
        active_inv = InvestmentDetail.objects.all().filter(_status = 'Active')
        context['active_inv'] = active_inv.count()

        # Queryset to calsulate total number of Active Members
        active_members = StaffAPI.objects.all()
        context['active_members'] = active_members.count()

        # Sum up all investments interest field
        
        print(context)
        return context





# Creating List View for model
@method_decorator(login_required, name='dispatch')
class InvestmentListView(ListView):
    context_object_name = 'investment_list'
    model = InvestmentDetail
    template_name = 'dashboard/investment_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        # Grouping Investment based on Types
        context['inv_type_t_bill'] = queryset.filter(investment_type='T-bills')
        context['inv_type_f_dep'] = queryset.filter(investment_type='F-deposit')
        context['inv_type_d_int'] = queryset.filter(investment_type='D-interest')

        # Getting queryset for each investment type
        t_bill_queryset = queryset.filter(investment_type='T-bills')
        f_deposit_queryset = queryset.filter(investment_type='F-deposit')
        d_interest_queryset = queryset.filter(investment_type='D-interest')

        # Paginating for each Tab-Pane
        t_bill_page = self.request.GET.get('t_bill_page',1)
        f_deposit_page = self.request.GET.get('f_deposit_page',1)
        d_interest_page = self.request.GET.get('d_interest_page',1)


        # Returning context keys for each page and applying pagination
        context['t_bill_page'] = Paginator(t_bill_queryset, per_page=2).get_page(t_bill_page)
        context['f_deposit_page'] = Paginator(f_deposit_queryset,2).get_page(f_deposit_page)
        context['d_interest_page'] = Paginator(d_interest_queryset,10).get_page(d_interest_page)


        # Counting Number of individual Investments
        context['investment_count']= queryset.count()
        context['T_bills_count'] = queryset.filter(investment_type='T-bills').count()
        context['F_deposit_count'] = queryset.filter(investment_type='F-deposit').count()
        context['D_interest_count'] = queryset.filter(investment_type='D-interest').count()
        
        return context
    

# Investment Detail View
@method_decorator(login_required, name='dispatch')
class InvestmentDetailView(DetailView):
    model = InvestmentDetail
    template_name = 'dashboard/investment_details.html'
    context_object_name = 'investment_detail'

# Adding an investment
@method_decorator(login_required, name='dispatch')
class AddInvestment(CreateView):
    model=InvestmentDetail
    fields = ('investment_type','account_name','account_type','account_number','principal_amount','interest_start_date','interest_end_date','interest_percentage')
    template_name = 'dashboard/investment_form.html'
    success_url = reverse_lazy('investment_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['account_type'] = InvestmentDetail.account
        return context

# Updating an Investement's details
@method_decorator(login_required, name='dispatch')
class InvestmentUpdateView(UpdateView):
    model = InvestmentDetail
    fields = ('investment_type','account_name','account_type','account_number','principal_amount','interest_start_date','interest_end_date','interest_percentage')
    # form_class = InvestmentUpdateForm
    template_name = 'dashboard/investment_form.html'

# Updating rollover interest percentage field only
@method_decorator(login_required, name='dispatch')
class RolloverPercentage(UpdateView):
    model = InvestmentDetail
    fields =('rollover_interest_percentage',)
    context_object_name = 'rollover'
    template_name = 'dashboard/rollover_percentage.html'

# Deleting an Investment from Database
@method_decorator(login_required, name='dispatch')
class InvestmentDeleteView(DeleteView):
    model = InvestmentDetail
    context_object_name = 'investment'
    template_name = 'dashboard/delete_investment.html'
    success_url = reverse_lazy('investment_list')


# Active Members List
@method_decorator(login_required, name='dispatch')
class MemberListView(ListView):
    # model = Member
    model = StaffAPI
    template_name = 'dashboard/member_list.html'
    # context_object_name = 'member_list'

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
class ExitedMembers(ListView):
    model = StaffAPI
    template_name ='dashboard/exited_members.html'
    paginate_by=20

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
class MemberDetailView(DetailView):
    # model = Member
    model = StaffAPI
    template_name = 'dashboard/member_details.html'


# Updating an member's details
@method_decorator(login_required, name='dispatch')
class MemberUpdateView(UpdateView):
    # model = Member
    model = StaffAPI
    fields = ('Staffnumber','status')
    template_name = 'dashboard/member_form.html'
    

# Deleting a member from Database
@method_decorator(login_required, name='dispatch')
class MemberDeleteView(DeleteView):
    # model = Member
    model = StaffAPI
    template_name = 'dashboard/delete_member.html'
    success_url = reverse_lazy('member_list')


from django.utils import timezone
from datetime import datetime

# Query For Investment View
@method_decorator(login_required, name='dispatch')
class InvestmentQuery(ListView):
    template_name = 'dashboard/query.html'
    model = InvestmentDetail
    paginate_by = 10
    # context_object_name = 'results'

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
        queryset = InvestmentDetail.objects.all()

        # A list to accumulate all related search before passing it as a context
        query=[]
        
        # If no date is specified
        if from_date == None and to_date == None:
            print('None date')
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
            print('Date')
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
class DelayedInterestListView(ListView):
    template_name = 'dashboard/delayed_interest_list.html'
    model = DelayedInterest
    paginate_by = 10
    context_object_name = 'delayed_interest'


@method_decorator(login_required, name='dispatch')
class DelayedInterestCreateView(CreateView):
    template_name = 'dashboard/delayed_interest_form.html'
    model = DelayedInterest
    fields = ('from_date','to_date','amount','remarks')
    success_url = reverse_lazy('delayed_interest_list')

@method_decorator(login_required, name='dispatch')
class BankInterestListView(ListView):
    template_name = 'dashboard/bank_interest_list.html'
    model = BankInterest
    paginate_by = 10
    context_object_name = 'bank_interest'

@method_decorator(login_required, name='dispatch')
class BankInterestCreateView(CreateView):
    template_name = 'dashboard/bank_interest_form.html'
    model = BankInterest
    fields = ('bank_name','from_date','to_date','amount','remarks','branch','account_number')
    success_url = reverse_lazy('bank_interest_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['banks'] = BankInterest.names
        return context




# Bank Interest Query
@method_decorator(login_required, name='dispatch')
class BankInterestQuery(ListView):
    model = BankInterest
    template_name = 'dashboard/bank_interest_query.html'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['banks'] = BankInterest.names

        from_date = self.request.GET.get('from-date')
        to_date = self.request.GET.get('to-date')
        bank = self.request.GET.get('bank_name')

        # convert 'date' to date format
        from_date = datetime.strptime(from_date,"%Y-%m-%d").date() if from_date else None

        to_date = datetime.strptime(to_date,"%Y-%m-%d").date() if to_date else None

        # get all bank interest data
        queryset = BankInterest.objects.all()

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
class DelayedInterestQuery(ListView):
    model = DelayedInterest
    template_name = 'dashboard/delayed_interest_query.html'
    paginate_by = 20


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get search elements from user

        from_date = self.request.GET.get('from-date')
        to_date = self.request.GET.get('to-date')

        # convert 'date' to date format
        from_date = datetime.strptime(from_date,"%Y-%m-%d").date() if from_date else None

        to_date = datetime.strptime(to_date,"%Y-%m-%d").date() if to_date else None

        # Fetch all Delayed Interest
        queryset = DelayedInterest.objects.all()

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
    
