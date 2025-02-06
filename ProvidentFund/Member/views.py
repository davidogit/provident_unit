from collections import defaultdict
from datetime import datetime, timedelta
from itertools import chain
import json,uuid
import smtplib
from typing import Any
from django.contrib.auth import authenticate, login, logout
from django.forms import ValidationError
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, JsonResponse
from django.urls import reverse, reverse_lazy
from django.views import View
import phonenumbers
import requests
from ProvidentFund.settings import EMAIL_HOST_USER
from .forms import UserForm, MemberForm
from .generate_otp import generate_unique_code
from smtplib import SMTPConnectError
from django.views.generic import TemplateView,UpdateView,CreateView,ListView
from django.contrib.auth.models import Group
from .models import Member,SchemeApproval, Transaction,ExitApproval
from django.utils.decorators import method_decorator
from Member.decorators import tenant_required,tenant_login_required
from Admin.decorators import role_required
from .forms import CombinedProfileForm
from MultiScheme.models import Tenant,InvestmentScheme
from contributions.models import Contribution, Membership, StaffAPI
# Importing the user model 
from django.contrib.auth import get_user_model
# Importing custom decorators
from .decorators import unauthenticated_user
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
# Import task to send otp via email
from .tasks import send_otp_code,gen_send_email
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.views.decorators.http import require_GET
from django.db import models
from django.http import JsonResponse
from django.views import View
from django.db.models import Sum
from contributions.models import StaffAPI
from .models import InvestmentScheme
import json
from django.views import View
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from .models import WithdrawalRequest
from decimal import Decimal
from django.db import transaction
from django.views import View
from django.shortcuts import render
from django.http import JsonResponse
from django.core.mail import send_mail
from django.utils import timezone
from phonenumbers import parse as parse_phone, format_number, PhoneNumberFormat
from twilio.rest import Client
import logging
from .models import WithdrawalRequest, InvestmentScheme, StaffAPI, Tenant, Transaction
from django.db.models import F


@unauthenticated_user
def registrationView(request,tenant_id):
    if request.method == 'POST':
        form1 = UserForm(request.POST)
        form2 = MemberForm(request.POST)

        if form1.is_valid() and form2.is_valid():
            
            # Making sure the person is a member of a tenant in our DB before registering them onto the system
            try:
                # Assign tenant to user upon registration
                tenant = request.tenant
                form1.instance.tenant = tenant

                # Check from API to see if member is there
                response = requests.get(tenant.api_endpoint_member)
                response.raise_for_status() #if theres an error trying to get a response from endpoint
                data = response.json()

                # loops and stops when it gets a match of a user and returns None if theres no match
                api_user = next((api_user for api_user in data if str(api_user.get('staff_number')) == str(request.POST.get('staff_id'))), None)

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

    tenant = request.tenant

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
 
                    try:
                        otp = generate_unique_code()
                        # Send OTP to user via email
                        send_otp_code.delay(user.email,EMAIL_HOST_USER,otp)

                        request.session['otp_token'] = otp
                        request.session['username'] = username
                        request.session['email'] = user.email
                    except SMTPConnectError as e:
                        print(f'SMTPConnectError: {e}')
                        return render(request, 'login_error.html', {'error': 'Failed to send email'})

                    # Redirect to verify_otp view
                    # return redirect('verify_otp', user_id=user.id, tenant_id=tenant_id)
                    redirect_url = reverse('verify_otp', kwargs={'user_id':user.id, 'tenant_id':tenant_id})
                    return JsonResponse({'status':'success', 'redirect_url':redirect_url})
                else:
                    # Redirect to invalid_login_details view
                    # return redirect('invalid_login_details', tenant_id=tenant_id)
                    return JsonResponse({'status':'error', 'message':'Invalid Login, Try again.'})
            else:
                # Redirect to invalid_login_details view
                # return redirect('invalid_login_details', tenant_id=tenant_id)
                return JsonResponse({'status':'error', 'message':'Invalid Login, Try again.'})
        
        else:
            # Redirect to invalid_login_details view
            # return redirect('invalid_login_details', tenant_id=tenant_id)
            return JsonResponse({'status':'error', 'message':'Invalid Login, Try again.'})

    return render(request, 'login.html')



class InvalidLoginDetails(TemplateView):
    template_name = 'login_error.html'



def verifyOtpView(request, user_id, tenant_id):
    # Assign tenant_id to request for further use
    request.tenant = tenant_id

    # Get user object or return a 404 if not found
    user = get_object_or_404(get_user_model(), id=user_id)

    # Get user email from session for displaying in the template
    user_email = request.session.get('email')

    # Handle POST request (when the form is submitted)
    if request.method == 'POST':
        # Get the individual OTP digits from POST data
        otp_1 = request.POST.get('otp-1', '')
        otp_2 = request.POST.get('otp-2', '')
        otp_3 = request.POST.get('otp-3', '')
        otp_4 = request.POST.get('otp-4', '')

        # Concatenate OTP parts into one string and convert to integer
        otp_combined = otp_1 + otp_2 + otp_3 + otp_4
        try:
            otp = int(otp_combined)  # Convert to integer
        except ValueError:
            return JsonResponse({'status': 'error', 'message': 'Invalid OTP format.'})

        # Retrieve OTP stored in session
        session_otp = request.session.get('otp_token')

        # If OTP is not set in the session, handle the expired or missing OTP case
        if session_otp is None:
            return JsonResponse({'status': 'error', 'message': 'OTP has expired or is not set.'}, status=400)

        # Validate OTP
        if otp == int(session_otp):
            # Set the custom authentication backend for the tenant-based login
            user.backend = 'Member.backends.TenantAwareBackend'
            login(request, user)  # Log the user in

            # Clear OTP from session after successful login
            del request.session['otp_token']

            # Check if the user belongs to the 'Member' group
            if user.groups.filter(name='Member').exists():
                # Get the related member and staff_id
                member = Member.objects.get(user=user)
                redirect_url = reverse('member_dashboard', kwargs={'tenant_id': tenant_id, 'member_id': member.staff_id})
                return JsonResponse({'status': 'success', 'redirect_url': redirect_url})

            # Handle non-member users, assuming redirection to finance page
            else:
                redirect_url = reverse('finance_page', kwargs={'tenant_id': tenant_id})
                return JsonResponse({'status': 'success', 'redirect_url': redirect_url})

        else:
            # Return error if OTP is incorrect
            return JsonResponse({'status': 'error', 'message': 'Invalid OTP.'})

    # For GET request, render the OTP form page
    return render(request, 'verify_otp.html', {'email': user_email})


@method_decorator(tenant_login_required, name="dispatch")
def logoutView(request, tenant_id):
    logout(request)
    return redirect('landing_page',tenant_id=tenant_id)


def terms_and_conditions_view(request):
    # Render the terms and conditions template
    return render(request, 'terms_and_conditions.html')




@method_decorator(tenant_login_required, name="dispatch")
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
        # tenant = self.request.tenant
        member_id = kwargs.get('member_id')
        member = self.request.user.member

        if member.staff_id == member_id:
            # user = get_object_or_404(Member, tenant=tenant, staff_id=member_id)
            context['staff_member'] = member
        else:
            context['staff_member'] = None

        return context




@method_decorator(tenant_login_required, name="dispatch")
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
        member = self.request.user.member
        return member


    def form_valid(self, form):
        form.save()
        return redirect('member_profile', tenant_id=self.request.tenant.id, member_id=self.get_object().staff_id)



# Member Scheme Application View

@method_decorator(tenant_login_required, name="dispatch")
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

            active_schemes = staff.investment_scheme.count()
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
            context['active_schemes_count']=active_schemes
            context['pending_schemes'] = pending_scheme
            context['pending_schemes_count'] = pending_scheme.count()
            context['days_since_joined']= days_since_joined

        return context





# View for Scheme Application
@method_decorator(tenant_login_required, name="dispatch")
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
            associated_schemes = staff.investment_scheme.values_list('id', flat=True)

            # associated_schemes = SchemeApproval.objects.filter(tenant=tenant,staff=staff).values_list('scheme_id', flat=True)
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
        # print(f"Form is invalid: {form.errors}")
        return super().form_invalid(form)
        
    def form_valid(self, form):
        tenant = self.request.tenant
        member = self.request.user.member
        scheme_id = self.request.POST.get('scheme_id')
        document = self.request.FILES.get('document')

        if document:
            # print(f'Document Details: Name:{document.name} size: {document.size}')
            pass

        if document and document.size > 2 * 1024 * 1024: #file size shouldnt be greater than 2MB
            return JsonResponse({'status':'error','message':'File size bigger than 2MB'})

        # Get staff using member.staff_id
        try:
            staff = get_object_or_404(StaffAPI,tenant=tenant,staff_number=member.staff_id)
        except StaffAPI.DoesNotExist:
            # print('Staff does not exist')
            return self.form_invalid(form)
        
        # print(f'{tenant},{member},{staff}')
        try:
            scheme = get_object_or_404(InvestmentScheme,tenant=tenant,id=scheme_id)
        except Exception:
            return JsonResponse({'status':'error', 'message':'The selected scheme is not available at the moment'})

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
                form.instance.document = document

                # Save form
                form.save()

                # Send Application successful email to user and application email to Management
                try:
                    # Email to user through tasks
                    subject='Scheme Application Successful'
                    message=f'Your application to join "{scheme}" is successfuly received, you will be notified when your application is approved by management'
                    recipient = self.request.user.email
                    gen_send_email.delay(recipient,message,subject)


                    # Email to Management through tasks
                    subject='Scheme Application Received'
                    message=f'{self.request.user.member.staff_id} has applied to join {scheme}. Review and approve application in due time'
                    recipient=tenant.email
                    gen_send_email.delay(recipient,message,subject)

                except smtplib.SMTPException:
                    email_error_message = 'There was an issue sending you a confirmation email, but your application was submitted successfuly and you will be notified when application is approved via email. Thank you'
                    return JsonResponse({'status':'error', 'message':email_error_message}, status=400)

                # Success prompt to user

                return JsonResponse({'status':'success','message':'Application sent successfully.'}, status=200)
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
    

@method_decorator(tenant_login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Member']), name='dispatch')
class ActiveSchemes(ListView):
    template_name = 'active_schemes.html'
    model = InvestmentScheme

    def dispatch(self, request, *args, **kwargs):
        member_id = kwargs.get('member_id')
        tenant = request.tenant
        member = request.user.member

        if request.method == 'POST':
            return self.handle_post(request,*args,**kwargs)
        
        
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
                # related_schemes = SchemeApproval.objects.filter(tenant=tenant,approved_by_hr=True,staff=staff).values_list('scheme_id', flat=True)

                # Filter Schemes based on related schemes
                # active_schemes = InvestmentScheme.objects.filter(tenant=tenant, id__in=related_schemes)
                active_schemes = staff.investment_scheme.all()
                
                context['active_schemes'] = active_schemes
            except Exception:
                context['active_schemes'] = []
        return context
    
    # Using dispatch to access post request in listview
    def handle_post(self,request,*args,**kwargs):
        tenant = request.tenant
        scheme_id = self.request.POST.get('scheme_id')
        member_id = self.request.POST.get('member_id')
        user = self.request.user.member

        reason_1 = self.request.POST.get('reason1')
        reason_2 = self.request.POST.get('reason2')
        reason_3 = self.request.POST.get('reason3')
        reason_4 = self.request.POST.get('reason4')
        reason_5 = self.request.POST.get('reason5')
        reason_6 = self.request.POST.get('other')
        custom_reason = self.request.POST.get('custom_reason')
        print(f'REASON: {custom_reason}')
        print(f'REASON 1: {reason_1}')

        reason_list = [
            reason_1,
            reason_2,
            reason_3,
            reason_4,
            reason_5,
            reason_6
        ]

        # look for which reason with value
        reason = ''
        for r in reason_list:
            if r:
                # if user chose 'other' then reason should be custom reason
                if r == 'other':
                    reason = custom_reason if custom_reason else ''
                else:
                    reason = r
                break

        try:
            # Get member and remove selected scheme from their list of schemes
            member = StaffAPI.objects.get(tenant=tenant,staff_number=member_id)
            # print(f'member_id: {member_id}')

            # Get scheme object
            scheme = InvestmentScheme.objects.get(tenant=tenant,id=scheme_id)
            
            # Approval Phase of Opt-out by management
            # ################################
            # Remove scheme from users schemes
            if member and scheme and user:
                # member.investment_scheme.remove(scheme)

                # Check database if user has an application sent already
                potential_application = ExitApproval.objects.filter(member=user,staff=member,tenant=tenant,scheme=scheme,approved=False).exists()

                # Prevent user from sending more than one exit application
                if potential_application:
                    return JsonResponse({'status':'error', 'message':'You already have an application sent. wait for approval'})


                # create exit instance for user
                
                ExitApproval.objects.create(
                    tenant = tenant,
                    member = user,
                    staff = member,
                    scheme = scheme,
                    reason = reason
                )
                return JsonResponse({'status':'success','message':'Application received. You will be notified after further review of your application'})


            ##################################

        except Exception as e:
            return JsonResponse({'status':'error', 'message': str(e)}, status=400)


    


@method_decorator(tenant_login_required, name="dispatch")
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
    
    # Delete pending scheme
    def post(self,request,*args,**kwargs):
        if request.method == 'POST':
            tenant = request.tenant
            scheme_id = self.request.POST.get('scheme_id')
            member = self.request.user.member

            print(f'DEL SCH: {tenant},{scheme_id},{member}')
            
            if scheme_id and tenant and member:
                SchemeApproval.objects.get(tenant=tenant,member=member,scheme__id=scheme_id).delete()
                return JsonResponse({'status':'success', 'message':'scheme application withdrawn successfully'})
            else:
                return JsonResponse({'status':'error', 'message':'Error deleting scheme'})

            
    

@method_decorator(tenant_login_required, name="dispatch")
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
        member = StaffAPI.objects.filter(staff_number=member_id, investment_scheme__tenant=tenant).first()

        # Set default year to current year if not provided
        if not selected_year:
            selected_year = datetime.now().year

        # Filter the contributions based on the member, scheme, tenant, and selected year
        if tenant and scheme_id:
            member_contributions=Contribution.objects.filter(
                member=member,
                investment_scheme__id=scheme_id,
                investment_scheme__tenant=tenant,
                year=selected_year,
                approved_contribution=True
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


logger = logging.getLogger(__name__)
@method_decorator(tenant_login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Member']), name='dispatch')
class CreateTransactionView(View):
    template_name = 'create_transaction.html'

    def get(self, request, *args, **kwargs):
        tenant = request.tenant
        schemes = InvestmentScheme.objects.filter(tenant=tenant)
        reference = str(uuid.uuid4())  # Pre-generate a unique reference

        context = {
            'schemes': schemes,
            'PAYSTACK_PUBLIC_KEY': settings.PAYSTACK_PUBLIC_KEY,
            'reference': reference,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            tenant = request.tenant
            staff_id = kwargs.get('staff_id')
            scheme_id = data.get('scheme_id')
            amount = data.get('amount')
            email = data.get('email')
            reference = data.get('reference')

            if not all([scheme_id, amount, email, reference]):
                return JsonResponse({'status': 'error', 'message': 'Missing required fields.'}, status=400)

            with transaction.atomic():
                scheme = InvestmentScheme.objects.get(tenant=tenant, id=scheme_id)
                staff = StaffAPI.objects.get(staff_number=staff_id)

                if Transaction.objects.filter(reference=reference).exists():
                    return JsonResponse({'status': 'error', 'message': 'Duplicate reference detected.'}, status=400)

                amount_in_kobo = int(float(amount) * 100)
                transaction_obj = Transaction.objects.create(
                    tenant=tenant,
                    staff=staff,
                    # member=member,
                    scheme=scheme,
                    amount=amount,
                    reference=reference
                )

                staff.total_contribution = F('contributions') + amount
                staff.save(update_fields=['contributions'])

                history_url = reverse('transaction_history', kwargs={
                    'tenant_id': tenant.id,
                    'staff_id':  staff.staff_number
                })

                return JsonResponse({
                    'status': 'success',
                    'transaction_reference': transaction_obj.reference,
                    'amount': amount_in_kobo,
                    'email': email,
                    'redirect_url': history_url
                })

        except json.JSONDecodeError:
            logger.error("Invalid JSON in request body")
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON in request body'}, status=400)
        except InvestmentScheme.DoesNotExist:
            logger.error(f"Invalid scheme ID: {scheme_id}")
            return JsonResponse({'status': 'error', 'message': 'Invalid scheme ID.'}, status=400)
        except StaffAPI.DoesNotExist:
            logger.error(f"Staff not found for member: {staff_id}")
            return JsonResponse({'status': 'error', 'message': 'Staff not found.'}, status=400)
        except Exception as e:
            logger.error(f"Unexpected error in CreateTransactionView: {str(e)}")
            return JsonResponse({'status': 'error', 'message': 'An unexpected error occurred.'}, status=500)

    @staticmethod
    def verify_transaction(reference):
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        response = requests.get(f"https://api.paystack.co/transaction/verify/{reference}", headers=headers)
        response.raise_for_status()
        return response.json()



@require_GET
def verify_transaction(request, reference):
    try:
        response = CreateTransactionView.verify_transaction(reference)
        if response['data']['status'] == 'success':
            # Update your transaction status in the database here
            return JsonResponse({'status': 'success', 'message': 'Payment verified successfully'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Payment verification failed'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


@method_decorator(tenant_login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Member']), name='dispatch')

class TransactionView(ListView):
    model = Transaction
    template_name = 'transaction_history.html'
    paginate_by = 10
    context_object_name = 'transactions'

    def get_queryset(self):
        tenant = self.request.tenant
        staff_id = self.kwargs.get('staff_id')
        staff = get_object_or_404(StaffAPI, tenant=tenant, staff_number=staff_id)
        # Fetch deposit transactions
        deposit_transactions = Transaction.objects.filter(staff=staff, tenant=tenant).order_by('-transaction_date')
        return deposit_transactions

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        staff_id = self.kwargs.get('staff_id')
        sort = self.request.GET.get('sort', '-transaction_date')
        scheme_id = self.request.GET.get('scheme_id')
        status = self.request.GET.get('status')

        try:
            staff = get_object_or_404(StaffAPI, tenant=tenant, staff_number=staff_id)
            context['schemes'] = staff.investment_scheme.all()

            # Fetch deposit and withdrawal transactions
            deposit_transactions = self.get_queryset().order_by(sort)
            withdrawal_requests = WithdrawalRequest.objects.filter(staff=staff, tenant=tenant).order_by('-request_date')

            # Filter by scheme if needed
            if scheme_id:
                deposit_transactions = deposit_transactions.filter(scheme__id=scheme_id)
                withdrawal_requests = withdrawal_requests.filter(scheme__id=scheme_id)

            # Filter by status if needed
            if status:
                deposit_transactions = deposit_transactions.filter(status=status)
                withdrawal_requests = withdrawal_requests.filter(approved=(status.lower() == 'completed'))

            # Combine and sort by date
            combined_transactions = sorted(
                chain(deposit_transactions, withdrawal_requests),
                key=lambda x: x.transaction_date if hasattr(x, 'transaction_date') else x.request_date,
                reverse=True
            )

            context['transactions'] = combined_transactions

        except StaffAPI.DoesNotExist:
            context['error'] = 'No transaction data available for this user'

        return context

    



logger = logging.getLogger(__name__)

class WithdrawalView(View):
    template_name = 'withdrawal.html'

    def get(self, request, *args, **kwargs):
        tenant = request.tenant
        schemes = InvestmentScheme.objects.filter(tenant=tenant)
        
        context = {
            'schemes': schemes,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            tenant = request.tenant
            member = request.user.member
            scheme_id = data.get('scheme_id')
            amount = data.get('amount')

            # Validate inputs
            if not all([scheme_id, amount]):
                return JsonResponse({'status': 'error', 'message': 'Missing required fields.'}, status=400)

            # Convert amount to Decimal for calculations
            amount = Decimal(amount)

            with transaction.atomic():
                # Validate scheme and staff
                scheme = InvestmentScheme.objects.get(tenant=tenant, id=scheme_id)
                staff = StaffAPI.objects.get(staff_number=member.staff_id)

                # Check if the user has sufficient balance
                balance = WithdrawalRequest.objects.filter(
                    tenant=tenant,
                    staff=staff,
                    scheme=scheme
                ).aggregate(balance=models.Sum('amount'))['balance'] or 0

                if balance < amount:
                    return JsonResponse({'status': 'error', 'message': 'Insufficient balance.'}, status=400)

                # Create a withdrawal request
                withdrawal_request = WithdrawalRequest.objects.create(
                    tenant=tenant,
                    staff=staff,
                    scheme=scheme,
                    amount=amount,
                    approved=False,
                    request_date=timezone.now(),
                )

                # Notify manager and user
                self.notify_manager(member, amount, scheme)
                self.notify_user(member, amount, scheme)

                return JsonResponse({
                    'status': 'success',
                    'message': 'Withdrawal request submitted for approval. Notification sent to your email and phone.'
                })

        except Exception as e:
            logger.error(f"Unexpected error in WithdrawalView: {str(e)}")
            return JsonResponse({'status': 'error', 'message': 'An unexpected error occurred.'}, status=500)

    def notify_manager(self, member, amount, scheme):
        try:
            manager_email = 'osahdav@gmail.com'  # Replace with dynamic manager email if available
            subject = 'Withdrawal Request Pending Approval'
            message = (
                f"A withdrawal request has been submitted by {member.user.get_full_name()} ID: {member.staff_id}.\n"
                f"Details:\n"
                f"Scheme: {scheme.name}\n"
                f"Amount: ₵{amount:.2f}\n"
                f"Status: Pending Approval\n"
                f"Please review and take the necessary actions."
            )

            send_mail(
                subject,
                message,
                'osahdav@gmail.com',  # Replace with your sender email
                [manager_email],
                fail_silently=False,
            )

            logger.info(f"Notification email sent to {manager_email} for withdrawal request.")
        except Exception as e:
            logger.error(f"Error sending notification email: {str(e)}")

    def notify_user(self, member, amount, scheme):
        try:
            # Send email to the user
            subject = 'Withdrawal Request Submitted'
            message = (
                f"Dear {member.user.get_full_name()},\n"
                f"Your withdrawal request of ₵{amount:.2f} from the {scheme.name} scheme has been submitted successfully.\n"
                f"Please note that it is pending approval and may take 2-3 business days to process."
            )

            send_mail(
                subject,
                message,
                'dave21620@gmail.com',  # Replace with your sender email
                [member.user.email],
                fail_silently=False,
            )

            raw_phone = member.tel_number
            parsed_phone = parse_phone(raw_phone, "GH")  # "GH" is the country code for Ghana
            if not phonenumbers.is_valid_number(parsed_phone):
                raise ValueError(f"Invalid phone number: {raw_phone}")
            formatted_phone = format_number(parsed_phone, PhoneNumberFormat.E164)

            # Send SMS to the user (using Twilio or another SMS service)
            account_sid = 'ACe6e705f0732d1a51651131aa2516ab10'
            auth_token = 'eb8dec355cd270700f0b00e341d3dc46'
            client = Client(account_sid, auth_token)

            sms_message = (
                f"Hi { member.user.last_name } { member.user.first_name }, your withdrawal request of ₵{amount:.2f} has been submitted. "
                f"It is pending approval and may take 2-3 business days."
            )

            client.messages.create(
                body=sms_message,
                from_='+14068004910',  # Replace with your Twilio phone number
                to=formatted_phone,  # Ensure the phone number is stored in the Member model
            )

            logger.info(f"Notification email and SMS sent to {member.user.email} and {member.formatted_phone}.")
        except Exception as e:
            logger.error(f"Error notifying user: {str(e)}")



class ManagerApprovalView(View):
    template_name = 'manager/approval_list.html'

    def get(self, request, *args, **kwargs):
        # Fetch pending withdrawal requests
        pending_requests = WithdrawalRequest.objects.filter(approved=False)

        context = {
            'pending_requests': pending_requests,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            withdrawal_id = data.get('withdrawal_id')
            action = data.get('action')

            # Validate input
            if not withdrawal_id or not action:
                return JsonResponse({'status': 'error', 'message': 'Missing required fields.'}, status=400)

            # Retrieve the withdrawal request
            withdrawal_request = get_object_or_404(WithdrawalRequest, id=withdrawal_id)

            if action == 'approve':
                # Approve the withdrawal request
                withdrawal_request.approved = True
                withdrawal_request.approval_date = timezone.now()
                withdrawal_request.save()

                # Process payment if needed
                self.process_payment(withdrawal_request)

            elif action == 'reject':
                # Reject the withdrawal request
                withdrawal_request.approved = False
                withdrawal_request.save()

                # Optionally refund the amount to the user's estimated profit
                staff = withdrawal_request.staff
                staff.estimated_profit += withdrawal_request.amount
                staff.save()

            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid action.'}, status=400)

            return JsonResponse({'status': 'success', 'message': 'Withdrawal request updated successfully.'})

        except Exception as e:
            logger.error(f"Error in ManagerApprovalView: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    def process_payment(self, withdrawal_request):
        """
        Process payment for an approved withdrawal request.
        """
        try:
            # Add payment processing logic here (e.g., MoMo, bank transfer)
            logger.info(f"Processing payment for withdrawal request ID: {withdrawal_request.id}")
            # Simulate payment success
        except Exception as e:
            logger.error(f"Error processing payment: {str(e)}")
            raise




class GetBalanceView(View):
    def get(self, request, tenant_id, staff_id, *args, **kwargs):
        scheme_id = request.GET.get('scheme_id')

        if not scheme_id:
            return JsonResponse(
                {'status': 'error', 'message': 'Scheme ID is required.'},
                status=400
            )

        try:
            # Fetch the investment scheme
            scheme = InvestmentScheme.objects.get(id=scheme_id)

            # Validate if the staff_id matches a valid Membership
            membership = Membership.objects.filter(
                scheme=scheme,
                staff__id=staff_id
            ).first()

            if not membership:
                return JsonResponse(
                    {'status': 'error', 'message': 'No membership found for this staff.'},
                    status=404
                )

            # Calculate the available balance
            available_balance = membership.total_earnings

            return JsonResponse({
                'status': 'success',
                'scheme_name': scheme.name,
                'balance': float(available_balance)
            })

        except InvestmentScheme.DoesNotExist:
            return JsonResponse(
                {'status': 'error', 'message': 'Invalid scheme ID.'},
                status=400
            )

        except Exception as e:
            return JsonResponse(
                {'status': 'error', 'message': str(e)},
                status=500
            )
