# from django.db.models.query import QuerySet
# from django.forms import BaseModelForm
# from django.http import HttpResponse
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.views.generic import TemplateView, ListView,DetailView,UpdateView,CreateView,DeleteView
# Create your views here.
from Fund.models import InvestmentDetail, Member
from django.urls import reverse_lazy
# from Fund.forms import InvestmentUpdateForm
from django.db.models import Sum, FloatField
from django.db.models.functions import Cast
from django.core.paginator import Paginator

from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required

@method_decorator(login_required, name='dispatch')
class Invest(TemplateView):
    template_name='dashboard/finance.html'


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


# Member List View
@method_decorator(login_required, name='dispatch')
class MemberListView(ListView):
    model = Member
    template_name = 'dashboard/member_list.html'
    context_object_name = 'member_list'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        context['member_count'] = self.get_queryset().count()

        return context
    

# Memeber detailed View
@method_decorator(login_required, name='dispatch')
class MemberDetailView(DetailView):
    model = Member
    template_name = 'dashboard/member_details.html'


# Member creating View
@method_decorator(login_required, name='dispatch')
class AddMemberView(CreateView):
    model = Member
    fields = ('first_name','last_name','staff_id')
    template_name = 'dashboard/member_form.html'
    success_url = reverse_lazy('member_list')

    def form_invalid(self, form):
        print(form.errors)  # Add this line to log the form errors
        return super().form_invalid(form)


# Updating an member's details
@method_decorator(login_required, name='dispatch')
class MemberUpdateView(UpdateView):
    model = Member
    fields = ('first_name','last_name','staff_id')
    template_name = 'dashboard/member_form.html'
    

# Deleting a member from Database
@method_decorator(login_required, name='dispatch')
class MemberDeleteView(DeleteView):
    model = Member
    template_name = 'dashboard/delete_member.html'
    success_url = reverse_lazy('member_list')




# Query For Investment View
@method_decorator(login_required, name='dispatch')
class InvestmentQuery(ListView):
    template_name = 'dashboard/query.html'
    model = InvestmentDetail

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        date = self.request.GET.get('date')
        inv_type = self.request.GET.get('inv_type')

        if date and inv_type:
            context['results'] = self.get_queryset().filter(created_date=date,investment_type=inv_type)
        elif date:
            context['results'] = self.get_queryset().filter(created_date=date)
        elif inv_type:
            context['results'] = self.get_queryset().filter(investment_type=inv_type)
        else:
            # Dont return anything
            pass
        return context