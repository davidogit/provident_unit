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

            # Create or Update staff details
            staff_member, created = StaffAPI.objects.update_or_create(
                Id=api_id,
                defaults={
                    'first_name': membership.get('first_name', ''),
                    'last_name': membership.get('last_name', ''),
                    'staff_number': membership.get('staff_number', ''),
                    'date_joined': membership.get('date_joined', ''),
                    'status': membership.get('status', ''),
                    'fund_type': membership.get('fund_type', ''),
                    'exited_date': exited_date,
                    'exited_flag': incoming_exited_flag,
                    'subscription_date': membership.get('subscription_date', ''),
                    # 'profit': membership.get('profit', 0),
                    # 'updated_date': membership.get('updated_date', ''),
                }
            )
                

        # Save every contribution from API 
        contrib_response = requests.get('https://6697f43902f3150fb66f9865.mockapi.io/api/v1/contribution')
        contributions = contrib_response.json()

        for contrib in contributions:
            date_str = contrib['contribution_date']
            # date_obj = datetime.strptime(date,"%Y-%m-%d").date() if date else None
            date_obj = parser.parse(date_str) if date_str else None

            # Get month and year from date
            month = date_obj.month if date_obj else None
            year = date_obj.year if date_obj else None

            # Fetch corresponding member
            member = StaffAPI.objects.get(Id = contrib['id'])

            Contribution.objects.update_or_create(
                member=member,
                month=month,
                year=year,
                defaults={
                    'employee_amount': contrib['employee_amount'],
                    'employer_amount': contrib['employer_amount'],
                    'retro_employee_amount': contrib['retro_employee_amount'],
                    'retro_employer_amount': contrib['retro_employer_amount'],
                    'contribution_date': contrib['contribution_date'],
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
        user_id = self.kwargs.get('membership_id')
        queryset = super().get_queryset().filter(member_id=user_id).order_by('contribution_date')
        # member_id
        
        selected_year = self.request.GET.get('year')
        if not selected_year:
            selected_year = datetime.now().year
        queryset = queryset.filter(contribution_date__year=selected_year)
        
        return queryset
    

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

        print(user_id)
        try:
            user = StaffAPI.objects.get(Id= user_id)


        except StaffAPI.DoesNotExist:
            user = None
        

        contributions = Contribution.objects.all().filter(member = user).order_by('contribution_date')
        context['contributions'] = contributions
        
        # print(contributions)

        monthly_contributions = defaultdict(list)


        for contribution in contributions:
            month_name = contribution.contribution_date.strftime('%B')
            monthly_contributions[month_name].append(contribution)
      
        context['monthly_contributions'] = dict(monthly_contributions)

        return context
