from django.urls import reverse
from django.views.generic import ListView, DetailView,TemplateView
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from .models import StaffAPI, Contribution
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.utils import timezone
from collections import defaultdict
from datetime import datetime
from django.core.mail import send_mail
from ProvidentFund.settings import EMAIL_HOST_USER
from django.template import loader
from MultiScheme.models import Tenant,InvestmentScheme
from django.shortcuts import render, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from Member.decorators import tenant_required,tenant_login_required
from Admin.decorators import role_required
from django.shortcuts import render, redirect



# Create your views here.

@method_decorator(tenant_login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['HR',]), name='dispatch')
class StaffMemberListView(ListView):
    model = StaffAPI
    template_name = 'contributions/staffmember_list.html'
    context_object_name = 'memberships'
    paginate_by = 5

    def get_queryset(self):

        # Get Tenant
        tenant = self.request.tenant
        # Get scheme name
        scheme_name = self.request.scheme_name

        if tenant and scheme_name:
            return StaffAPI.objects.filter(exited_flag=False,tenant=tenant,investment_scheme__id=scheme_name)
        else:
            return StaffAPI.objects.none()


@method_decorator(tenant_login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch') 
@method_decorator(role_required(role=['HR',]), name='dispatch')  
class OptOutMemberView(View):
    def post(self, request, *args, **kwargs):
        member_id = kwargs.get('pk')
        tenant = self.request.tenant
        scheme_id = request.scheme_name
        
        try:
            member = get_object_or_404(StaffAPI, pk=member_id,tenant=tenant)

            scheme = InvestmentScheme.objects.get(tenant=tenant,id=scheme_id)
            member.investment_scheme.remove(scheme)
            member.save()
            self.send_opt_out_email(member)
        except ObjectDoesNotExist:
            return JsonResponse({'status':'error', 'message':'Error: Cannot perform operation at this time.'})
        redirect_url = reverse('staff_member_list', kwargs={'tenant_id':tenant.id,'scheme_name':scheme_id})

        return JsonResponse({'status': 'success', 'message':'Successful removed staff from scheme', 'redirect_url':redirect_url}, status=200)

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


@method_decorator(tenant_login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['HR',]), name='dispatch')
class StaffMemberDetailView(DetailView):
    model = StaffAPI
    template_name = 'contributions/staffmember_detail.html'
    context_object_name = 'membership'


@method_decorator(tenant_login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['HR',]), name='dispatch')
class Contributed(ListView):
    model = Contribution
    template_name = 'contributions/contributed.html'
    # context_object_name = 'contributions'
    paginate_by = 12

    def get_queryset(self):
        # Get user id and year from Get request
        user_id = self.kwargs.get('pk')
        selected_year = self.request.GET.get('year')

        # Get tenant from middleware
        tenant = self.request.tenant

        # Get scheme id
        scheme_id = self.request.scheme_name

        # get staff instance using user_id and tenant
        user = StaffAPI.objects.filter(Id=user_id,tenant=tenant,investment_scheme__id=scheme_id).prefetch_related('contribution').first()

        if not selected_year:
            selected_year = datetime.now().year
        else:
            selected_year = str(selected_year)

        if tenant and scheme_id:
            contributions = user.contribution.filter(year=selected_year,approved_contribution=True)
            return contributions
        else:
            return contributions.none()

    
    # Using get_object to retrieve the user pk from url
    def get_object(self):
        user_id = self.kwargs.get('pk')
        tenant = self.request.tenant

        return get_object_or_404(StaffAPI, Id=user_id, investment_scheme__tenant=tenant)

    # context data
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        selected_year = self.request.GET.get('year')
        if not selected_year:
            selected_year = datetime.now().year 
        
        years = list(range(2020, datetime.now().year + 1))
        
        context['years'] = years
        context['selected_year'] = str(selected_year)

        
        contributions = self.get_queryset()
        context['contributions'] = contributions

        # Initialize monthly_contribution
        monthly_contributions = defaultdict(list)

        for contribution in contributions:
            month_name = contribution.contribution_date.strftime('%B')
            monthly_contributions[month_name].append(contribution)
      
        context['monthly_contributions'] = dict(monthly_contributions)

        return context