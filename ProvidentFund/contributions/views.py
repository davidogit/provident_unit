from django.shortcuts import render
from django.forms import BaseModelForm
from django.http import HttpResponse
from django.shortcuts import  redirect
from django.views.generic import TemplateView, ListView,DetailView
from .models import ContributionsDetail ,GeneralLedger
from django.urls import reverse_lazy
from Fund.models import Member
from .models import StaffMember, GeneralLedger, StaffAPI
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
# from .models import StaffMember

# Create your views here.
@method_decorator(login_required,name = "dispatch")
class Invest(TemplateView):
    template_name='dashboard/finance.html'

@method_decorator(login_required,name = "dispatch")
class ContributionsListView(ListView):
    context_object_name = 'memberships'
    model = StaffAPI
    template_name = 'contributions/contributions_list.html'
    paginate_by = 10
@method_decorator(login_required,name = "dispatch")
class ContributionsListView2(ListView):
    context_object_name = 'contributions_listpf2'
    model = ContributionsDetail
    template_name = 'contributions/contributions_listpf2.html'

    

# Investment Detail View
@method_decorator(login_required,name = "dispatch")
class ContributionsDetailView(DetailView):
    model = ContributionsDetail
    template_name = 'contributions/contributions_details.html'
    context_object_name = 'contributions_details'


# views.py

from django.views.generic import ListView, DetailView
from .models import StaffMember, GeneralLedger, StaffAPI
import requests
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required

@method_decorator(login_required,name = "dispatch")
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
    @method_decorator(login_required, name="dispatch")
    def get(self, request, *args, **kwargs):
        response = requests.get('https://66718737e083e62ee43bf829.mockapi.io/api/v1/addmembership')
        memberships = response.json()

        for membership in memberships:
            api_id = membership.get('Id')
            StaffAPI.objects.update_or_create(
                Id=api_id,
                defaults={
                    'Fullname': membership.get('Fullname', ''),
                    'Staffnumber': membership.get('Staffnumber', ''),
                    'Datejoined': membership.get('Datejoined', '1970-01-01'),
                    'status': membership.get('status', ''),
                    'Fundtype': membership.get('Fundtype', ''),
                    'EmployeeAmount': membership.get('EmployeeAmount', 0.0),
                    'EmployerAmount': membership.get('EmployerAmount', 0.0),
                    'RetroEmployeeAmount': membership.get('RetroEmployeeAmount', 0.0),
                    'RetroEmployerAmount': membership.get('RetroEmployerAmount', 0.0),
                    'Employee55Amount': membership.get('Employee55Amount', 0.0),
                    'Employer55Amount': membership.get('Employer55Amount', 0.0),
                    'RetroEmployee55Amount': membership.get('RetroEmployee55Amount', 0.0),
                    'RetroEmployer55Amount': membership.get('RetroEmployer55Amount', 0.0),
                    'ContributionDate': membership.get('ContributionDate', '1970-01-01'),
                }
            )
        return super().get(request, *args, **kwargs)

@method_decorator(login_required, name="dispatch")
class StaffMemberDetailView(DetailView):
    model = StaffAPI
    template_name = 'contributions/staffmember_detail.html'
    context_object_name = 'memberships'