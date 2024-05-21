from django.shortcuts import render
from django.views.generic import TemplateView
# Create your views here.


class Invest(TemplateView):
    template_name='dashboard/finance.html'


class AddInvestment(TemplateView):
    template_name = 'dashboard/addInvestment.html'

class InvestMentList(TemplateView):
    template_name= 'dashboard/investment_list.html'

class MemberList(TemplateView):
    template_name= 'dashboard/member_list.html'