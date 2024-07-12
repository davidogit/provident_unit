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

# Create your views here.

@method_decorator(login_required, name="dispatch")
class StaffMemberListView(ListView):
    model = StaffAPI
    template_name = 'contributions/staffmember_list.html'
    context_object_name = 'memberships'
    paginate_by = 5

    def get_queryset(self):
        return StaffAPI.objects.filter(exited_flag=False)

    @method_decorator(login_required, name="dispatch")
    def get(self, request, *args, **kwargs):
        response = requests.get('https://66718737e083e62ee43bf829.mockapi.io/api/v1/addmembership')
        memberships = response.json()

        for membership in memberships:
            incoming_exited_flag = membership.get('exited_flag', False)
            api_id = membership.get('Id')

            existing_staff_member = StaffAPI.objects.filter(Id=api_id).first()

            if existing_staff_member and existing_staff_member.exited_flag:
                continue

            if incoming_exited_flag:
                continue

            exited_date = membership.get('exited_date', None)
            if incoming_exited_flag and exited_date:
                exited_date = timezone.now() if not exited_date else exited_date
            else:
                exited_date = None
            staff_member, created = StaffAPI.objects.update_or_create(
                Id=api_id,
                defaults={
                    'first_name': membership.get('first_name', ''),
                    'last_name': membership.get('last_name', ''),
                    'staff_number': membership.get('staff_number', ''),
                    'date_joined': membership.get('date_joined', ''),
                    'status': membership.get('status', ''),
                    'fund_type': membership.get('fund_type', ''),
                    'employee_amount': membership.get('employee_amount', 0),
                    'employer_amount': membership.get('employer_amount', 0),
                    'retro_employee_amount': membership.get('retro_employee_amount', 0),
                    'retro_employer_amount': membership.get('retro_employer_amount', 0),
                    'contribution_date': membership.get('contribution_date', ''),
                    'exited_date': exited_date,
                    'exited_flag': incoming_exited_flag,
                    'profit': membership.get('profit', 0),
                    'subscription_date': membership.get('subscription_date', ''),
                    'updated_date': membership.get('updated_date', ''),
                 }
            )

            if 'contributions' in membership:
                for contrib in membership['contributions']:
                  Contribution.objects.update_or_create(
                    member=staff_member,
                    month=membership['month'],
                    year=membership['year'],
                    defaults={
                        'employee_amount': membership['employee_amount'],
                        'employer_amount': membership['employer_amount'],
                        'retro_employee_amount': membership['retro_employee_amount'],
                        'retro_employer_amount': membership['retro_employer_amount'],
                        'contribution_date': membership['contribution_date'],
                    }
                )
        return super().get(request, *args, **kwargs)


    



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
            'Notification Mail!',
            'osahdav@gmail.com',
            ['dave21620@gmail.com'],
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
        queryset = queryset.filter(contribution_date__year=selected_year)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        selected_year = self.request.GET.get('year')
        if not selected_year:
            selected_year = datetime.now().year 
        
        years = list(range(2020, datetime.now().year + 1))
        
        context['years'] = years
        context['selected_year'] = int(selected_year)
        
        contributions = self.get_queryset().order_by('contribution_date')

        monthly_contributions = defaultdict(list)
        for contribution in contributions:
            month_name = contribution.contribution_date.strftime('%B')
            monthly_contributions[month_name].append(contribution)
        
        context['monthly_contributions'] = dict(monthly_contributions)

        return context
