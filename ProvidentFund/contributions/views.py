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
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from decimal import Decimal

# Create your views here.

@method_decorator(tenant_login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Contributions Manager','Contributions Supervisor','Contributions Analyst']),name='dispatch')
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
            return StaffAPI.objects.filter(exited_flag=False,tenant=tenant,investment_scheme__id=scheme_name).order_by('-first_name')
        else:
            return StaffAPI.objects.none()


@method_decorator(tenant_login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Contributions Manager','Contributions Supervisor','Contributions Analyst']),name='dispatch')
class AjaxStaffSearchView(View):
    model = StaffAPI
    paginate_by = 10

    def get_queryset(self, *args, **kwargs):
        tenant = self.request.tenant
        scheme_id = self.request.scheme_name

        return self.model.objects.filter(
            tenant=tenant,
            investment_scheme__id=scheme_id
        ).order_by('-first_name')

    def get(self, *args, **kwargs):
        page = int(self.request.GET.get('page',1))
        queryset = self.get_queryset()
        search_term = self.request.GET.get('search','')
        status = self.request.GET.get('status','')

        if search_term:
            queryset=queryset.filter(
                Q(first_name__icontains=search_term)|
                Q(last_name__icontains=search_term)|
                Q(staff_number__icontains=search_term)
            )
        if status:
            queryset = queryset.filter(
                status=status
            )
        total_pages = 0
        current_page = 0
        if queryset.exists():
            paginator = Paginator(queryset,self.paginate_by)
            total_pages = paginator.num_pages

            try:
                paginated_queryset = paginator.page(page)
                current_page = paginated_queryset.number

            except PageNotAnInteger:
                paginated_queryset = paginator.page(1)
            except EmptyPage:
                paginated_queryset = paginator.page(paginator.num_pages)

            member_list = [
                {
                    'Id':member.Id,
                    'first_name':member.first_name,
                    'last_name':member.last_name,
                    'date_joined':member.date_joined,
                    'status':member.status,
                    'fund_type':member.fund_type,
                    'staff_number':member.staff_number
                }
                for member in paginated_queryset
            ]
        else:
            member_list = []
        
        return JsonResponse({
            'status':'success',
            'pagination':{
                'total_pages':total_pages,
                'current_page':current_page
            },
            'memberships':member_list
        })



@method_decorator(tenant_login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch') 
@method_decorator(role_required(role=[]), name='dispatch')  
class OptOutMemberView(View):
    def post(self, request, *args, **kwargs):
        member_id = kwargs.get('pk')
        tenant = self.request.tenant
        scheme_id = request.scheme_name
        
        
        try:
            member = get_object_or_404(StaffAPI, pk=member_id,tenant=tenant)

            scheme = InvestmentScheme.objects.get(
                tenant=tenant,
                id=scheme_id,
                approved=True
            )
            member.investment_scheme.remove(scheme)
            member.save()
            self.send_opt_out_email(member)
        except ObjectDoesNotExist:
            return JsonResponse({'status':'error', 'message':'Error: Cannot perform operation at this time.'})
        redirect_url = reverse('staff_member_list', kwargs={'tenant_id':tenant.id,'scheme_name':scheme_id})

        return JsonResponse({'status': 'success', 'message':'Successful removed staff from scheme', 'redirect_url':redirect_url}, status=200)

    def send_opt_out_email(self, member):
        recipient_email = member.email if member.email else 'providentfund@example.com' #fallback mail incase of no email
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
            recipient_list=[recipient_email],
            html_message=html_message,
            fail_silently=False,
        )


@method_decorator(tenant_login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Contributions Manager','Contributions Supervisor','Contributions Analyst']), name='dispatch')
class StaffMemberDetailView(DetailView):
    model = StaffAPI
    template_name = 'contributions/staffmember_detail.html'
    context_object_name = 'staff'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scheme_id = self.request.scheme_name
        member = self.get_object() #get the staff/member
        if member:
            scheme_account_balance = Decimal(0)
            scheme_estimated_earnings = Decimal(0)
            contributions = Decimal(0)
            date_joined = None
            related_schemes = None

            #exract the amount from selected scheme
            membership = member.membership.filter(scheme__id=scheme_id).first()
            if membership:
                scheme_account_balance = membership.total_earnings
                scheme_estimated_earnings = membership.estimated_profit
                date_joined = membership.enrolled_at

                # Get member contributions
                scheme_contributions = membership.staff.contribution.filter(
                    investment_scheme__id=scheme_id,
                    approved_contribution=True
                )
                for c in scheme_contributions:
                    contributions += c.total_contribution
                
                # Get related member schemes
                related_schemes = member.investment_scheme.all().exclude(id=scheme_id).values_list('name',flat=True)

            context.update(
                {
                    'scheme_account_balance':scheme_account_balance or Decimal(0),
                    'scheme_estimated_earnings':scheme_estimated_earnings or Decimal(0),
                    'scheme_contributions':contributions,
                    'date_joined':date_joined,
                    'related_schemes':related_schemes
                }
            )
        return context


@method_decorator(tenant_login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Contributions Manager','Contributions Supervisor','Contributions Analyst']), name='dispatch')
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
    # def get_object(self):
    #     user_id = self.kwargs.get('pk')
    #     tenant = self.request.tenant

    #     return get_object_or_404(StaffAPI, Id=user_id, investment_scheme__tenant=tenant)

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