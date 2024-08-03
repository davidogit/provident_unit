from typing import Any
from django.db.models.query import QuerySet
from django.views.generic import TemplateView, ListView, DetailView
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from .models import StaffAPI, Contribution
import requests
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views import View
from django.utils import timezone
from django.http import HttpResponseRedirect
from collections import defaultdict
from datetime import datetime
from django.shortcuts import redirect
from django.core.mail import send_mail
from django.conf import settings
from django.core.mail import EmailMessage
from ProvidentFund.settings import EMAIL_HOST_USER
import traceback
from django.template import loader
from django.template.loader import render_to_string
from django.db.models import Sum, F
from dateutil import parser
from MultiScheme.models import Tenant,InvestmentScheme

# Create your views here.

@method_decorator(login_required, name="dispatch")
class StaffMemberListView(ListView):
    model = StaffAPI
    template_name = 'contributions/staffmember_list.html'
    context_object_name = 'memberships'
    paginate_by = 5

    def get_queryset(self):

        # Get Tenant
        tenant_id = self.request.tenant.id
        tenant = Tenant.objects.get(id=tenant_id)

        # Get scheme name
        scheme_name = self.request.scheme_name
        scheme = InvestmentScheme.objects.get(id=scheme_name)

        if tenant and scheme_name:
            return StaffAPI.objects.filter(exited_flag=False,investment_scheme__tenant=tenant, investment_scheme=scheme)
        else:
            return StaffAPI.objects.none()

    

    



@method_decorator(login_required, name='dispatch')   
class OptOutMemberView(View):
    def post(self, request, *args, **kwargs):
        member_id = kwargs.get('pk')
        member = get_object_or_404(StaffAPI, pk=member_id)
        member.exited_date = timezone.now()
        member.exited_flag = True
        member.save()
        
        self.send_opt_out_email(member)
        
        return JsonResponse({'status': 'success'}, status=200)

    def send_opt_out_email(self, member):
        html_message = loader.render_to_string(
            'contributions/message.html',
            {
                'name': 'Admin',
                'body': f'This email is to confirm that {member.first_name} {member.last_name} has opted out of the pension fund system.',
            }
        )
        send_mail(
             subject='Notification Mail!',
            message='',  # Empty because we are sending html_message
            from_email=EMAIL_HOST_USER,
            recipient_list=['dave21620@gmail.com'],
            html_message=html_message,
            fail_silently=False,
        )


@method_decorator(login_required, name="dispatch")
class StaffMemberDetailView(DetailView):
    model = StaffAPI
    template_name = 'contributions/staffmember_detail.html'
    context_object_name = 'membership'


@method_decorator(login_required, name="dispatch")
class Contributed(ListView):
    model = Contribution
    template_name = 'contributions/contributed.html'
    # context_object_name = 'contributions'
    paginate_by = 12

    def get_queryset(self):
        # Get user id
        user_id = self.kwargs.get('membership_id')
        selected_year = self.request.GET.get('year')

        # Get tenant from middleware
        tenant = self.request.tenant
        # Get scheme name
        scheme_name = self.request.scheme_name

        if not selected_year:
            selected_year = datetime.now().year
        else:
            selected_year = selected_year

        if tenant and scheme_name:
            obj = Contribution.objects.filter(investment_scheme__tenant=tenant, investment_scheme__name=scheme_name)
            queryset = obj.filter(member_id=user_id,contribution_date__year=selected_year).order_by('contribution_date')
            return queryset
        else:
            return Contribution.objects.none()

    

    # Using get_object to retrieve the user pk from url
    def get_object(self):
        user_id = self.kwargs.get('membership_id')

        return get_object_or_404(StaffAPI, Id=user_id)





    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        selected_year = self.request.GET.get('year')
        if not selected_year:
            selected_year = datetime.now().year 
        
        years = list(range(2020, datetime.now().year + 1))
        
        context['years'] = years
        context['selected_year'] = str(selected_year)


        # Get user ID
        # user_id = 6
        user_id = self.kwargs.get('membership_id')

        try:
            user = StaffAPI.objects.get(Id= user_id)


        except StaffAPI.DoesNotExist:
            user = None
        

        contributions = self.get_queryset().filter(member = user)
        context['contributions'] = contributions
        
        # print(contributions)

        monthly_contributions = defaultdict(list)


        for contribution in contributions:
            month_name = contribution.contribution_date.strftime('%B')
            monthly_contributions[month_name].append(contribution)
      
        context['monthly_contributions'] = dict(monthly_contributions)

        return context
