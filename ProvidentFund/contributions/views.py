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

from Member.decorators import tenant_required
from Admin.decorators import role_required

# Create your views here.

@method_decorator(login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
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
            return StaffAPI.objects.filter(exited_flag=False,investment_scheme__tenant=tenant)
        else:
            return StaffAPI.objects.none()

    

    



@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')   
class OptOutMemberView(View):
    def post(self, request, *args, **kwargs):
        member_id = kwargs.get('pk')
        tenant = self.request.tenant

        member = get_object_or_404(StaffAPI, pk=member_id, investment_schene__tenant=tenant)
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
@method_decorator(tenant_required, name='dispatch')
class StaffMemberDetailView(DetailView):
    model = StaffAPI
    template_name = 'contributions/staffmember_detail.html'
    context_object_name = 'membership'


@method_decorator(login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
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
        user = get_object_or_404(StaffAPI, Id=user_id,investment_scheme__tenant=tenant)

        if not selected_year:
            selected_year = datetime.now().year
        else:
            selected_year = str(selected_year)

        if tenant and scheme_id:
            return Contribution.objects.filter(member = user,investment_scheme__id=scheme_id,investment_scheme__tenant=tenant,year=selected_year)
        else:
            return Contribution.objects.none()

    
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
    


    

@method_decorator(login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Member',]), name='dispatch')
class MemberPortal(TemplateView):
    template_name = 'contributions/staff_profile.html'

    # Overridind dispatch to redirect users trying to access others portal
    def dispatch(self, request, *args, **kwargs):
        member_id = kwargs.get('member_id')
        tenant = request.tenant
        
        # Retrieve the currently logged-in user's associated member
        member = request.user.member
        
        # Redirect if the user is trying to access someone else's profile
        if member.staff_id != member_id:
            return redirect('member_profile', tenant_id=tenant.id, member_id=member.staff_id)
        
        # Proceed with rendering the template if authorized
        return super().dispatch(request, *args, **kwargs)


    def get_context_data(self, **kwargs):
        context=super().get_context_data(**kwargs)

        tenant = self.request.tenant
        member_id = kwargs.get('member_id')
        print(f'{member_id} {tenant}')

        # make sure members dont alter url in order to view other members portal
        member = self.request.user.member

        if member.staff_id == member_id:

            user = get_object_or_404(StaffAPI,investment_scheme__tenant=tenant,staff_number=member_id)
            context['staff_member'] = user
        
        else:
            context['staff_member']=[]

        return context



# def staff_profile(request, staff_id):
#     tenant = request.tenant
#     staff_member = get_object_or_404(StaffAPI, Id=staff_id, investment_scheme__tenant=tenant)
#     return render(request, 'staff_profile.html', {'staff_member': staff_member})