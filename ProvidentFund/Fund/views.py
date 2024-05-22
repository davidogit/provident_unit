from django.forms import BaseModelForm
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.generic import TemplateView, ListView,DetailView,UpdateView,CreateView,DeleteView
# Create your views here.
from Fund.models import InvestmentDetail, Member
from django.urls import reverse_lazy
# from Fund.forms import AddInvestmentForm

class Invest(TemplateView):
    template_name='dashboard/finance.html'


# class MemberList(TemplateView):
#     template_name= 'dashboard/member_list.html'


# Creating List View for model
class InvestmentListView(ListView):
    context_object_name = 'investment_list'
    model = InvestmentDetail
    template_name = 'dashboard/investment_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        context['investment_count']= queryset.count()
        context['T_bills_count'] = queryset.filter(investment_type='T-bills').count()
        context['F_deposit_count'] = queryset.filter(investment_type='F-deposit').count()
        context['D_interest_count'] = queryset.filter(investment_type='D-interest').count()
        
        return context
    

# Investment Detail View
class InvestmentDetailView(DetailView):
    model = InvestmentDetail
    template_name = 'dashboard/investment_details.html'
    context_object_name = 'investment_detail'

# Adding an investment
class AddInvestment(CreateView):
    model=InvestmentDetail
    fields = ('investment_type','account_name','account_type','account_number','principal_amount','interest_amount','interest_start_date','interest_end_date','interest_percentage')
    template_name = 'dashboard/investment_form.html'
    success_url = reverse_lazy('investment_list')

# Updating an Investement's details
class InvestmentUpdateView(UpdateView):
    model = InvestmentDetail
    fields = ('investment_type','account_name','account_type','account_number','principal_amount','interest_amount','interest_start_date','interest_end_date','interest_percentage')
    template_name = 'dashboard/investment_form.html'


# Deleting an Investment from Database
class InvestmentDeleteView(DeleteView):
    model = InvestmentDetail
    template_name = 'dashboard/delete_investment.html'
    success_url = reverse_lazy('investment_list')


# Member List View
class MemberListView(ListView):
    model = Member
    template_name = 'dashboard/member_list.html'
    context_object_name = 'member_list'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['member_count'] = self.get_queryset().count()
        return context
    

# Memeber detailed View
class MemberDetailView(DetailView):
    model = Member
    template_name = 'dashboard/member_details.html'


# Member creating View
class AddMemberView(CreateView):
    model = Member
    fields = ('first_name','last_name','staff_id')
    template_name = 'dashboard/member_form.html'
    success_url = reverse_lazy('member_list')


# Updating an member's details
class MemberUpdateView(UpdateView):
    model = Member
    fields = ('first_name','last_name','staff_id')
    template_name = 'dashboard/member_form.html'
    

# Deleting a member from Database
class MemberDeleteView(DeleteView):
    model = Member
    template_name = 'dashboard/delete_member.html'
    success_url = reverse_lazy('member_list')