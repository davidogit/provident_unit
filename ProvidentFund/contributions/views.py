from django.shortcuts import render
from django.forms import BaseModelForm
from django.http import HttpResponse
from django.shortcuts import  redirect
from django.views.generic import TemplateView, ListView,DetailView
from .models import ContributionsDetail
from django.urls import reverse_lazy
from Fund.models import Member

# Create your views here.

class Invest(TemplateView):
    template_name='dashboard/finance.html'

# Creating List View for model
class ContributionsListView(ListView):
    context_object_name = 'contributions_list'
    model = ContributionsDetail
    template_name = 'contributions/contributions_list.html'

class ContributionsListView2(ListView):
    context_object_name = 'contributions_listpf2'
    model = ContributionsDetail
    template_name = 'contributions/contributions_listpf2.html'

    

# Investment Detail View
class ContributionsDetailView(DetailView):
    model = ContributionsDetail
    template_name = 'contributions/contributions_details.html'
    context_object_name = 'contributions_details'
