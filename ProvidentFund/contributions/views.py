from django.shortcuts import render
from django.forms import BaseModelForm
from django.http import HttpResponse
from django.shortcuts import  redirect
from django.views.generic import TemplateView, ListView,DetailView
from .models import ContributionsDetail ,GeneralLedger
from django.urls import reverse_lazy
from Fund.models import Member
from .models import StaffMember, GeneralLedger, StaffAPI
# from .models import StaffMember

# Create your views here.

class Invest(TemplateView):
    template_name='dashboard/finance.html'

# Creating List View for model
class ContributionsListView(ListView):
    context_object_name = 'memberships'
    model = StaffAPI
    template_name = 'contributions/contributions_list.html'
    paginate_by = 10

class ContributionsListView2(ListView):
    context_object_name = 'contributions_listpf2'
    model = ContributionsDetail
    template_name = 'contributions/contributions_listpf2.html'

    

# Investment Detail View
class ContributionsDetailView(DetailView):
    model = ContributionsDetail
    template_name = 'contributions/contributions_details.html'
    context_object_name = 'contributions_details'


# views.py

from django.views.generic import ListView, DetailView
from .models import StaffMember, GeneralLedger, StaffAPI
import requests

class StaffMemberListView(ListView):
    model = StaffAPI
    template_name = 'contributions/staffmember_list.html'
    context_object_name = 'memberships'
    paginate_by = 5

    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     response = requests.get('https://6662e51362966e20ef0a7cdb.mockapi.io/api/v1/addmembership')
    #     context['memberships'] = response.json()
    #     return context

    def get(self, request, *args, **kwargs):
        response = requests.get('https://6662e51362966e20ef0a7cdb.mockapi.io/api/v1/addmembership')
        memberships = response.json()
        
        for membership in memberships:
            StaffAPI.objects.update_or_create(
                Id=membership['Id'],
                defaults={
                    'Fullname': membership['Fullname'],
                    'Staffnumber': membership['Staffnumber'],
                    'Datejoined': membership['Datejoined'],
                    'status' : membership['status'],
                    'Fundtype' : membership['Fundtype'],
                    'EmployeeAmount' : membership['EmployeeAmount'], 
                    'EmployerAmount' : membership['EmployerAmount'],
                    'RetroEmployeeAmount': membership['RetroEmployeeAmount'],
                    'RetroEmployerAmount': membership['RetroEmployerAmount'],
                    'Employee55Amount': membership['Employee55Amount'],
                    'Employer55Amount' : membership['Employee55Amount'],
                    'RetroEmployee55Amount': membership['RetroEmployee55Amount'], 
                    'RetroEmployer55Amount' : membership['RetroEmployer55Amount'],
                    'ContributionDate': membership['ContributionDate'],
                }
            )
        return super().get(request, *args, **kwargs)
    





class StaffMemberDetailView(DetailView):
    model = StaffAPI
    template_name = 'contributions/staffmember_detail.html'
    context_object_name = 'memberships'

