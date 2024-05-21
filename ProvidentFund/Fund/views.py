from django.forms import BaseModelForm
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.generic import TemplateView, ListView,DetailView,UpdateView,CreateView
# Create your views here.
from Fund.models import InvestmentDetail
from django.urls import reverse_lazy
# from Fund.forms import AddInvestmentForm

class Invest(TemplateView):
    template_name='dashboard/finance.html'


class MemberList(TemplateView):
    template_name= 'dashboard/member_list.html'


# Creating List View for model
class InvestmentListView(ListView):
    context_object_name = 'investment_list'
    model = InvestmentDetail
    template_name = 'dashboard/investment_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['investment_count'] = self.get_queryset().count()
        return context
    

# Adding an investment

class AddInvestment(CreateView):
    model=InvestmentDetail
    fields = ('account_name','account_type','account_number','principal_amount','interest_amount','interest_start_date','interest_end_date','interest_percentage')
    template_name = 'dashboard/addInvestment.html'
    success_url = reverse_lazy('investment_list')

