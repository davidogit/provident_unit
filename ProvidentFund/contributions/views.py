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
from django.core.mail import send_mail
from django.template import loader
from django.template.loader import render_to_string


# Create your views here.

@method_decorator(login_required,name = "dispatch")
class StaffMemberListView(ListView):
    model = StaffAPI
    template_name = 'contributions/staffmember_list.html'
    context_object_name = 'memberships'
    paginate_by = 5

    def get_queryset(self):
        return StaffAPI.objects.filter(ExitedFlag=False)

    
    @method_decorator(login_required, name="dispatch")
    def get(self, request, *args, **kwargs):
        response = requests.get('https://66718737e083e62ee43bf829.mockapi.io/api/v1/addmembership')
        memberships = response.json()

        for membership in memberships:
            incoming_exited_flag = membership.get('ExitedFlag', False)
            api_id = membership.get('Id')

            # Fetch the existing staff member if exists
            existing_staff_member = StaffAPI.objects.filter(Id=api_id).first()

            # Check if the existing or incoming ExitedFlag is True
            if existing_staff_member and existing_staff_member.ExitedFlag:
                continue  # Skip update or create if existing ExitedFlag is True

            if incoming_exited_flag:
                continue  # Skip update or create if incoming ExitedFlag is True

            # Proceed to update or create if checks pass
            ExitedDate = membership.get('ExitedDate', None)
            if incoming_exited_flag and ExitedDate:
                ExitedDate = timezone.now() if not ExitedDate else ExitedDate
            else:
                ExitedDate = None
            staff_member, created = StaffAPI.objects.update_or_create(
                Id=api_id,
                defaults={
                    'Fullname': membership.get('Fullname', ''),
                    'Staffnumber': membership.get('Staffnumber', ''),
                    'Datejoined': membership.get('Datejoined', ''),
                    'status': membership.get('status', ''),
                    'Fundtype': membership.get('Fundtype', ''),
                    'EmployeeAmount': membership.get('EmployeeAmount', 0.0),
                    'EmployerAmount': membership.get('EmployerAmount', 0.0),
                    'RetroEmployeeAmount': membership.get('RetroEmployeeAmount', 0.0),
                    'RetroEmployerAmount': membership.get('RetroEmployerAmount', 0.0),
                    'ContributionDate': membership.get('ContributionDate', ''),
                    'ExitedDate': ExitedDate,
                    'ExitedFlag': incoming_exited_flag,
                 }
            )

            # Update the contribution details
            if 'contributions' in membership:
                for contrib in membership['contributions']:
                    Contribution.objects.update_or_create(
                        member=staff_member,
                        month=contrib['month'],
                        year=contrib['year'],
                        defaults={
                            'EmployeeAmount': contrib['EmployeeAmount'],
                            'EmployerAmount': contrib['EmployerAmount'],
                            'RetroEmployeeAmount': contrib['RetroEmployeeAmount'],
                            'RetroEmployerAmount': contrib['RetroEmployerAmount'],
                            'ContributionDate': contrib['ContributionDate'],
                        }
                    )
        return super().get(request, *args, **kwargs)
    

    
@method_decorator(login_required, name='dispatch')   
class OptOutMemberView(View):
    def post(self, request, *args, **kwargs):
        member_id = kwargs.get('pk')
        member = get_object_or_404(StaffAPI, pk=member_id)
        member.ExitedDate = timezone.now()
        member.ExitedFlag = True
        member.save()
        
        # Send email to admin
        self.send_opt_out_email(member)
        
        return JsonResponse({'status': 'success'}, status=200)

    def send_opt_out_email(self, member):
        # Inject the respective values in HTML template
        html_message = loader.render_to_string(
            'contributions/message.html',
            {
                'name': 'Eben',  # TODO: Enter the recipient name
                'body': 'This email is to verify whether we can send email in Django from Gmail account.',
                'sign': 'Sender',  # TODO: Update the signature
            }
        )
        send_mail(
            'Congratulations!',
            'You are lucky to receive this mail.',
            'osahdav@gmail.com',  # TODO: Update this with your mail id
            ['dave21620@gmail.com'],  # TODO: Update this with the recipients mail id
            html_message=html_message,
            fail_silently=False,
        )
@method_decorator(login_required, name='dispatch')
class StaffMemberDetailView(DetailView):
    model = StaffAPI
    template_name = 'contributions/staffmember_detail.html'
    context_object_name = 'membership'

    


@method_decorator(login_required, name="dispatch")
class Contributed(ListView):
    model = Contribution
    template_name = 'contributions/contributed.html'
    context_object_name = 'contributions'
    paginate_by = 12

    def get_queryset(self):
        user_id = self.kwargs.get('membership_id')
        queryset = super().get_queryset().filter(member_id=user_id)
        
        selected_year = self.request.GET.get('year')
        if not selected_year:
            selected_year = datetime.now().year
        queryset = queryset.filter(ContributionDate__year=selected_year)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        selected_year = self.request.GET.get('year')
        if not selected_year:
            selected_year = datetime.now().year 
        
        years = list(range(2020, datetime.now().year + 1))
        
        context['years'] = years
        context['selected_year'] = int(selected_year)
        
        contributions = self.get_queryset().order_by('ContributionDate')

        monthly_contributions = defaultdict(list)
        for contribution in contributions:
            month_name = contribution.ContributionDate.strftime('%B')
            monthly_contributions[month_name].append(contribution)
        
        context['monthly_contributions'] = dict(monthly_contributions)

        return context
