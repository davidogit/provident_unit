from collections import defaultdict
from datetime import datetime, timedelta
import smtplib
from typing import Any
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.core.mail import send_mail
from django.urls import reverse
import requests
from ProvidentFund.settings import EMAIL_HOST_USER
from django.contrib.auth.decorators import login_required
from .forms import UserForm, MemberForm
from .generate_otp import generate_unique_code
from smtplib import SMTPConnectError
from django.views.generic import TemplateView,UpdateView,CreateView,ListView,View,DeleteView
from django.contrib.auth.models import Group
from .models import Member,SchemeApproval
from django.utils.decorators import method_decorator
from Member.decorators import tenant_required
from Admin.decorators import role_required
from .forms import CombinedProfileForm
from MultiScheme.models import Tenant,InvestmentScheme
from contributions.models import Contribution, StaffAPI
# Importing the user model 
from django.contrib.auth import get_user_model
# Importing custom decorators
from .decorators import unauthenticated_user
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist


@unauthenticated_user
def registrationView(request,tenant_id):
    if request.method == 'POST':
        form1 = UserForm(request.POST)
        form2 = MemberForm(request.POST)

        if form1.is_valid() and form2.is_valid():
            
            # Making sure the person is a member of a tenant in our DB before registering them onto the system
            try:
                # Assign tenant to user upon registration
                tenant = Tenant.objects.get(id=tenant_id)
                form1.instance.tenant = tenant

                # Check from API to see if member is there
                response = requests.get(tenant.api_endpoint_contribution)
                response.raise_for_status() #if theres an error trying to get a response from endpoint
                data = response.json()
                print(data)

                # loops and stops when it gets a match of a user and returns None if theres no match
                api_user = next((api_user for api_user in data if str(api_user.get('staff_number')) == str(request.POST.get('staff_id'))), None)
                # print(request.POST.get('staff_id'))
                # for api_user in data:
                    # print(api_user.get('staff_number'))
                    
                # print(request.POST.get('staff_id'))
                # Checks if the differece between joined_date and current date is greter than eligibility criteria
                if api_user:
            

                    user = form1.save(commit=False)
                    cleaned_password = form1.cleaned_data['password']
                    user.set_password(cleaned_password)
                    user.save()

                    # Assign group to user
                    group_name = 'Member'
                    group = Group.objects.get(name=group_name)
                    user.groups.add(group)

                    # Assign tenant to user upon registration
                    form2.instance.tenant = tenant

                    member = form2.save(commit=False)
                    member.user = user

                    member.save()

                    # redirect to login page after successful registration
                    return redirect('login', tenant_id = tenant_id)
                else:
                    return HttpResponse('Your details do not match any of our records')

            # Handle cases where there is no Scheme or Bad request
            except requests.RequestException as e:
                return HttpResponse(f'Error contacting external server:{e}')
        else:
            errors = form1.errors.as_json() + form2.errors.as_json()
            return HttpResponse(f'Some fields are invalid: {errors}')
    else:
        form1 = UserForm()
        form2 = MemberForm()

    return render(request, 'register.html', {'form1': form1, 'form2': form2})


@unauthenticated_user
def loginView(request, tenant_id):

    tenant = Tenant.objects.get(id=tenant_id)

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password,tenant=tenant)

        if user is not None:

            # Redirect anyone with admin priviledge
            if user.groups.filter(name='Admin'):
                return redirect('invalid_login_details', tenant_id=tenant_id)

            if user is not None:
                if user.tenant == tenant:
                    # Generate OTP
                    otp = generate_unique_code()
                    try:
                        # Send OTP to user via email
                        send_mail(
                            subject='PF CODE',
                            message=f'Your OTP code is {otp}',
                            from_email=EMAIL_HOST_USER,
                            recipient_list=[user.email],
                            fail_silently=False,
                        )

                        # Save OTP in session for later verification
                        request.session['otp_token'] = otp
                        request.session['username'] = username
                        request.session['email'] = user.email
                    except SMTPConnectError as e:
                        print(f'SMTPConnectError: {e}')
                        return render(request, 'login_error.html', {'error': 'Failed to send email'})

                    # Redirect to verify_otp view
                    return redirect('verify_otp', user_id=user.id, tenant_id=tenant_id)
                else:
                    # Redirect to invalid_login_details view
                    return redirect('invalid_login_details', tenant_id=tenant_id)
            else:
                # Redirect to invalid_login_details view
                return redirect('invalid_login_details', tenant_id=tenant_id)
        
        else:
            # Redirect to invalid_login_details view
            return redirect('invalid_login_details', tenant_id=tenant_id)

    return render(request, 'login.html')



class InvalidLoginDetails(TemplateView):
    template_name = 'login_error.html'





def verifyOtpView(request,user_id, tenant_id):
    request.tenant = tenant_id

    # Get user object
    user = get_object_or_404(get_user_model(), id=user_id)

    # Get user email from session
    user_email = request.session.get('email')
    if request.method == 'POST':
        otp_1 = request.POST.get('otp-1','')
        otp_2 = request.POST.get('otp-2','')
        otp_3 = request.POST.get('otp-3','')
        otp_4 = request.POST.get('otp-4','')

        # concantenate otp
        otp_combined = otp_1+otp_2+otp_3+otp_4
        # convert otp from string to integer
        otp = int(otp_combined)

        # Retrieve OTP from session
        session_otp = request.session.get('otp_token')

        # Check if theres session_otp for cases where there is no session_otp
        if session_otp is None:
            return HttpResponse('OTP has expired or is not set', status=400)

        if otp == int(session_otp):
            # we manually set the auth backend to our backend so it can authenticate based on the tenant
            user.backend = 'Member.backends.TenantAwareBackend'

            login(request, user)
            
            # Clear session data after successful login
            del request.session['otp_token']


            if user.groups.filter(name='Member'):
                # Get related member to user and extract staff_id from Member
                member = Member.objects.get(user=user)                
                return redirect('member_dashboard', tenant_id=tenant_id, member_id=member.staff_id)
            else:
                return redirect('finance_page', tenant_id)
        else:
            return HttpResponse('Invalid OTP')

    return render(request, 'verify_otp.html',{'email':user_email})


@login_required
def logoutView(request, tenant_id):
    logout(request)
    return redirect('landing_page',tenant_id=tenant_id)


def terms_and_conditions_view(request):
    # Render the terms and conditions template
    return render(request, 'terms_and_conditions.html')




@method_decorator(login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Member']), name='dispatch')
class MemberPortal(TemplateView):
    template_name = 'staff_profile.html'

    def dispatch(self, request, *args, **kwargs):
        member_id = kwargs.get('member_id')
        tenant = request.tenant
        member = request.user.member
        
        if member.staff_id != member_id:
            return redirect('member_dashboard', tenant_id=tenant.id, member_id=member.staff_id)
        
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        member_id = kwargs.get('member_id')
        member = self.request.user.member

        if member.staff_id == member_id:
            user = get_object_or_404(Member, tenant=tenant, staff_id=member_id)
            context['staff_member'] = user
        else:
            context['staff_member'] = None

        return context




@method_decorator(login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Member']), name='dispatch')
class EditMemberProfileView(UpdateView):
    model = Member
    form_class = CombinedProfileForm
    template_name = 'edit_member_profile.html'
    context_object_name = 'member'

    def dispatch(self, request, *args, **kwargs):
        member_id = kwargs.get('member_id')
        tenant = request.tenant
        member = request.user.member
        
        if member.staff_id != member_id:
            return redirect('member_dashboard', tenant_id=tenant.id, member_id=member.staff_id)
        
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        member_id = self.kwargs.get('member_id')
        return get_object_or_404(Member, staff_id=member_id)

    # def get_form_kwargs(self):
    #     kwargs = super().get_form_kwargs()
    #     kwargs['instance'] = self.get_object()
    #     kwargs['user_instance'] = self.request.user  # Passing user separately
    #     return kwargs

    def form_valid(self, form):
        form.save()
        return redirect('member_profile', tenant_id=self.request.tenant.id, member_id=self.get_object().staff_id)



# Member Scheme Application View

@method_decorator(login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Member']), name='dispatch')
class MemberDashboard(TemplateView):
    template_name = 'member_home_page.html'

    def dispatch(self, request, *args, **kwargs):
        member_id = kwargs.get('member_id')
        tenant = request.tenant
        member = request.user.member
        
        if member.staff_id != member_id:
            return redirect('member_dashboard', tenant_id=tenant.id, member_id=member.staff_id)
        
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        staff_id = self.request.user.member.staff_id

        try:
            staff = get_object_or_404(StaffAPI,tenant=tenant, staff_number=staff_id)

            days_since_joined = (timezone.now().date()-staff.date_joined).days


            # APPROVED SCHEMES
            
            ################################################
            approved_schemes = SchemeApproval.objects.filter(tenant=tenant,staff=staff,approved_by_hr=True).values_list('scheme_id', flat=True)

            schemes = InvestmentScheme.objects.filter(tenant=tenant)
            active_schemes = schemes.filter(id__in=approved_schemes)


            #################################################

            # PENDING SCHEMES

            ################################################
            pending_schemes = SchemeApproval.objects.filter(tenant=tenant,staff=staff,approved_by_hr=False).values_list('scheme_id', flat=True)

            schemes = InvestmentScheme.objects.filter(tenant=tenant)
            pending_scheme = schemes.filter(id__in=pending_schemes)

            #################################################
        except StaffAPI.DoesNotExist:
            staff = None

        if tenant and staff:
            context['staff'] = staff
            context['active_schemes']=active_schemes
            context['active_schemes_count']=active_schemes.count()
            context['pending_schemes'] = pending_scheme
            context['pending_schemes_count'] = pending_scheme.count()
            context['days_since_joined']= days_since_joined

        return context





# View for Application

@method_decorator(login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Member']), name='dispatch')
class Application(CreateView):
    model = SchemeApproval
    fields = []
    template_name = 'scheme_application.html'

    def dispatch(self, request, *args, **kwargs):
        member_id = kwargs.get('member_id')
        tenant = request.tenant
        member = request.user.member
        
        if member.staff_id != member_id:
            return redirect('member_dashboard', tenant_id=tenant.id, member_id=member.staff_id)
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        staff_id = self.request.user.member.staff_id

        # Retrieve staff
        try:
            staff = get_object_or_404(StaffAPI, tenant=tenant, staff_number=staff_id)

            # Get staff's schemes both approved and unapproved
            # associated_schemes = staff.investment_scheme.all()

            associated_schemes = SchemeApproval.objects.filter(tenant=tenant,staff=staff).values_list('scheme_id', flat=True)
            # unapproved staff schemes: Omit schemes that are pending for a user

            # Get Scheme approvals based on tenant and member
            pending_schemes_approval = SchemeApproval.objects.filter(tenant=tenant,staff=staff,approved_by_hr=False)

            context['pending_scheme_approvals'] = pending_schemes_approval
            
        except StaffAPI.DoesNotExist:
            staff = None
        

        if tenant:
            try:
                schemes = InvestmentScheme.objects.filter(tenant=tenant)
                filtered_scheme = schemes.exclude(id__in=associated_schemes)
                context['available_scheme']=filtered_scheme
                
            except InvestmentScheme.DoesNotExist:
                context['available_scheme']=[]

        return context
    
    def form_invalid(self, form):
        print(f"Form is invalid: {form.errors}")
        return super().form_invalid(form)
        
    def form_valid(self, form):
        tenant = self.request.tenant
        member = self.request.user.member
        scheme_id = self.request.POST.get('scheme_id')

        # Get staff using member.staff_id
        try:
            staff = get_object_or_404(StaffAPI,tenant=tenant,staff_number=member.staff_id)
        except StaffAPI.DoesNotExist:
            # print('Staff does not exist')
            return self.form_invalid(form)
        
        # print(f'{tenant},{member},{staff}')
        scheme = get_object_or_404(InvestmentScheme,tenant=tenant,id=scheme_id)

        # Check for eligibility before submitting application

        eligibility_in_days = scheme.eligibility_criteria_months*30 #convert months to days for calculation
        eligible_date = timezone.now().date() - timedelta(eligibility_in_days) # returns a date value

        if staff.date_joined<=eligible_date:

            if tenant and member and staff:
                form.instance.tenant = tenant
                form.instance.member = member
                form.instance.staff = staff
                form.instance.scheme = scheme
                form.instance.application_date = timezone.now()

                # Save form
                form.save()

                # Send Application successful email to user and application email to Management
                try:
                    # Email to user
                    send_mail(
                        subject='Scheme Application Successful',
                        message=f'Your application to join "{scheme}" is successfuly received, you will be notified when your application is approved by management',
                        from_email=EMAIL_HOST_USER,
                        recipient_list=[self.request.user.email],
                        fail_silently=False
                    )

                    # Email to Management
                    send_mail(
                        subject='Scheme Application Received',
                        message=f'{self.request.user.member.staff_id} has applied to join {scheme}. Review and approve application in due time',
                        from_email=EMAIL_HOST_USER,
                        recipient_list=[tenant.email],
                        fail_silently=False
                    )
                except smtplib.SMTPException:
                    email_error_message = 'There was an issue sending you a confirmation email, but your application was submitted successfuly and you will be notified when application is approved via email. Thank you'
                    return JsonResponse({'status':'error', 'message':email_error_message}, status=400)

                # Success prompt to user

                return JsonResponse({'status':'success'}, status=200)
            else:
                message = 'Some required fields are missing'
                return JsonResponse({'status':'error', 'message':message}, status=400)
        else:
            message = 'You are not eligigble to apply for this scheme at this moment. Try again later'
            return JsonResponse({'status':'error', 'message':message}, status=400)
        
        

    def get_success_url(self):
        tenant = self.request.tenant
        user = self.request.user.member.staff_id
        return reverse('member_dashboard', kwargs={'tenant_id':tenant.id, 'member_id':user})
    

@method_decorator(login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Member']), name='dispatch')
class ActiveSchemes(ListView):
    template_name = 'active_schemes.html'
    model = InvestmentScheme

    def dispatch(self, request, *args, **kwargs):
        member_id = kwargs.get('member_id')
        tenant = request.tenant
        member = request.user.member
        
        if member.staff_id != member_id:
            return redirect('member_dashboard', tenant_id=tenant.id, member_id=member.staff_id)
        
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get tenant
        tenant = self.request.tenant
        user_id = self.request.user.member.staff_id

        try:
            staff = StaffAPI.objects.get(tenant=tenant,staff_number=user_id)
        except ObjectDoesNotExist:
            staff=None

        # Get queryset
        if tenant and staff:
            try:
                # Get related schems of user from SchemeApproval
                related_schemes = SchemeApproval.objects.filter(tenant=tenant,approved_by_hr=True,staff=staff).values_list('scheme_id', flat=True)

                # Filter Schemes based on related schemes
                active_schemes = InvestmentScheme.objects.filter(tenant=tenant, id__in=related_schemes)
                
                context['active_schemes'] = active_schemes
            except SchemeApproval.DoesNotExist:
                return None
        return context
    


@method_decorator(login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Member']), name='dispatch')
class PendingSchemes(ListView):
    template_name = 'pending_schemes.html'
    model = InvestmentScheme

    def dispatch(self, request, *args, **kwargs):
        member_id = kwargs.get('member_id')
        tenant = request.tenant
        member = request.user.member
        
        if member.staff_id != member_id:
            return redirect('member_dashboard', tenant_id=tenant.id, member_id=member.staff_id)
        
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get tenant
        tenant = self.request.tenant
        user_id = self.request.user.member.staff_id

        try:
            staff = StaffAPI.objects.get(tenant=tenant,staff_number=user_id)
        except ObjectDoesNotExist:
            staff=None

        # Get queryset
        if tenant and staff:
            try:
                # Get related schems of user from SchemeApproval
                related_schemes = SchemeApproval.objects.filter(tenant=tenant,approved_by_hr=False,staff=staff).values_list('scheme_id', flat=True)

                # Filter Schemes based on related schemes
                pending_schemes = InvestmentScheme.objects.filter(tenant=tenant, id__in=related_schemes)
                
                context['pending_schemes'] = pending_schemes
            except SchemeApproval.DoesNotExist:
                return None
        return context
    

@method_decorator(login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Member']), name='dispatch')
class Contributed(ListView):
    model = Contribution
    template_name = 'member_contributions.html'  # Template for contributions page
    paginate_by = 12  # Optional, for paginating the contributions list

    def dispatch(self, request, *args, **kwargs):
        member_id = kwargs.get('member_id')
        tenant = request.tenant
        member = request.user.member
        
        if member.staff_id != member_id:
            return redirect('member_dashboard', tenant_id=tenant.id, member_id=member.staff_id)
        
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        # Get the member_id and year from the request
        member_id = self.kwargs.get('member_id')
        selected_year = self.request.GET.get('year')

        # Get tenant and scheme details from the request
        tenant = self.request.tenant
        scheme_id = self.request.scheme_name

        # Retrieve the member (StaffAPI) instance based on the tenant and staff number
        member = get_object_or_404(StaffAPI, staff_number=member_id, investment_scheme__tenant=tenant)

        # Set default year to current year if not provided
        if not selected_year:
            selected_year = datetime.now().year

        # Filter the contributions based on the member, scheme, tenant, and selected year
        if tenant and scheme_id:
            member_contributions=Contribution.objects.filter(
                member=member,
                investment_scheme__id=scheme_id,
                investment_scheme__tenant=tenant,
                year=selected_year
            )
            return member_contributions
        else:
            return Contribution.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get selected year and list of years for dropdown
        selected_year = self.request.GET.get('year', datetime.now().year)
        years = list(range(2020, datetime.now().year + 1))

        context['years'] = years
        context['selected_year'] = str(selected_year)

        # Get contributions and organize them by month
        contributions = self.get_queryset()
        context['contributions'] = contributions

        # Group contributions by month
        monthly_contributions = defaultdict(list)
        for contribution in contributions:
            month_name = contribution.contribution_date.strftime('%B')
            monthly_contributions[month_name].append(contribution)
    
        context['monthly_contributions'] = dict(monthly_contributions)

        return context

   