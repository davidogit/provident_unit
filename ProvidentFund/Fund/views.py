from django.forms import BaseModelForm
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.generic import TemplateView, ListView,DetailView,UpdateView,CreateView,DeleteView
# Create your views here.
from Fund.models import InvestmentDetail, Member
from django.urls import reverse_lazy
from Fund.forms import InvestmentUpdateForm
from django.db.models import Sum,F, FloatField
from django.db.models.functions import Cast

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

        context['inv_type_t_bill'] = queryset.filter(investment_type='T-bills')
        context['inv_type_f_dep'] = queryset.filter(investment_type='F-deposit')
        context['inv_type_d_int'] = queryset.filter(investment_type='D-interest')
        context['investment_count']= queryset.count()
        context['T_bills_count'] = queryset.filter(investment_type='T-bills').count()
        context['F_deposit_count'] = queryset.filter(investment_type='F-deposit').count()
        context['D_interest_count'] = queryset.filter(investment_type='D-interest').count()

        # calculating interest based on interest rate


        for investment in queryset:
            inv_principal = investment.principal_amount
            inv_principal = float(inv_principal)
            inv_rate = investment.interest_percentage
            inv_rate = float(inv_rate)

            if inv_principal != 0.0 and inv_rate !=0.0:
                inv_return = ((inv_rate)/100)*inv_principal
            else:
                inv_return = 0.0

            investment.interest_amount = inv_return
            # Saving newly calculated return to database
            investment.save()
        
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
    # form_class = InvestmentUpdateForm
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
        queryset = self.get_queryset()
        context['member_count'] = self.get_queryset().count()

        # calculate total contribution
        total_contribution = queryset.aggregate(total=Sum(Cast('total_amount_to_date',FloatField())*1.0))['total'] or 0.0

        # calculating total profit
        total_profit = InvestmentDetail.objects.aggregate(total=Sum(Cast('interest_amount',FloatField())*1.0))['total'] or 0.0

        # Individual profit calculation

        for member in queryset:
            member_contribution = member.total_amount_to_date or 0.0
            member_contribution = float(member_contribution)

            if total_contribution !=0:
                member_profit = ((member_contribution)/(total_contribution))*total_profit
            else:
                member_profit = 0.0

            member.profit = member_profit
            # save new profit to database
            member.save()

        context['member_list']= queryset
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