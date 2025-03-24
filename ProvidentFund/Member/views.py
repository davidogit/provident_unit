from datetime import datetime, timedelta
import json,uuid
import smtplib
from typing import Any
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.views import View
import requests
from ProvidentFund.settings import EMAIL_HOST_USER
from .forms import UserForm, MemberForm
from .generate_otp import generate_unique_code
from smtplib import SMTPConnectError
from django.views.generic import TemplateView,UpdateView,CreateView,ListView
from django.contrib.auth.models import Group
from .models import Member,SchemeApproval, Transaction,ExitApproval,WithdrawalRequest
from django.utils.decorators import method_decorator
from Member.decorators import tenant_required,tenant_login_required
from Admin.decorators import role_required
from .forms import CombinedProfileForm
from MultiScheme.models import InvestmentScheme, TenantEventNotification
from contributions.models import Contribution, Membership, StaffAPI
# Importing the user model 
from django.contrib.auth import get_user_model
# Importing custom decorators
from .decorators import unauthenticated_user
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from django.views.decorators.http import require_GET
from django.db.models import Sum
from decimal import Decimal
from django.db import transaction
import logging
from django.db.models import F
from .tasks import notify_user_email_sms,notify_withdrawal_approval,send_otp_code,gen_send_email

logger = logging.getLogger(__name__)

# Registration View
@method_decorator(unauthenticated_user, name='dispatch')
class MemberRegistrationView(TemplateView):
    template_name = 'register.html'

    def post(self, request, *args, **kwargs):
        tenant = self.request.tenant
        user_data = UserForm(request.POST)
        member_data = MemberForm(request.POST)

        if user_data.is_valid() and member_data.is_valid():
            # Set tenant on user_form and member_form
            user_data.instance.tenant = tenant
            member_data.instance.tenant = tenant

            # Check with endpoint if staff ID exists
            url = tenant.api_endpoint_member

            api_user_data = None
            try:
                api_response = requests.get(url, timeout=10)
                api_response.raise_for_status()
                
                data = api_response.json()
                api_user_data = any(member['staff_number'] == member_data.cleaned_data['staff_id'] for member in data)

                if not api_user_data:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'No matching staff ID found in database.'
                    })
                            
            except requests.ConnectionError:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Unable to reach external server, please try again.'
                })
            except requests.Timeout:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Request timed out.'
                })
            except requests.RequestException as req_exc:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Request error occurred: {str(req_exc)}'
                })

            # Get group for user
            try:
                user_group = Group.objects.get(name='Member')
            except Exception:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Could not get user assigned group.'
                })
            
            with transaction.atomic():
                # Process and Save user/member data
                user = user_data.save(commit=False)
                user.set_password(user_data.cleaned_data['password1'])  # Ensure correct field
                user.save()

                # Assign group
                user.groups.add(user_group)

                # Set relationship between user and member
                member = member_data.save(commit=False)
                member.user = user
                member.save()

                return JsonResponse({
                    'status': 'success',
                    'redirect_url': self.get_success_url()
                })
        else:
            # Capture and return specific form errors, including password validation issues
            errors = {**user_data.errors, **member_data.errors}
            return JsonResponse({
                'status': 'error',
                'message': 'Form validation failed.',
                'errors': errors  # Detailed error messages
            })

    def get_success_url(self):
        tenant_id = self.request.tenant.id
        return reverse('login', kwargs={'tenant_id': tenant_id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form1'] = UserForm()
        context['form2'] = MemberForm()
        return context


# @unauthenticated_user
# def registrationView(request,tenant_id):
#     if request.method == 'POST':
#         form1 = UserForm(request.POST)
#         form2 = MemberForm(request.POST)

#         if form1.is_valid() and form2.is_valid():
            
#             # Making sure the person is a member of a tenant in our DB before registering them onto the system
#             try:
#                 # Assign tenant to user upon registration
#                 tenant = request.tenant
#                 form1.instance.tenant = tenant

#                 # Check from API to see if member is there
#                 response = requests.get(tenant.api_endpoint_member)
#                 response.raise_for_status() #if theres an error trying to get a response from endpoint
#                 data = response.json()

#                 # loops and stops when it gets a match of a user and returns None if theres no match
#                 api_user = next((api_user for api_user in data if str(api_user.get('staff_number')) == str(request.POST.get('staff_id'))), None)

#                 # Checks if the differece between joined_date and current date is greter than eligibility criteria
#                 if api_user:
#                     user = form1.save(commit=False)
#                     cleaned_password = form1.cleaned_data['password']
#                     user.set_password(cleaned_password)
#                     user.save()

#                     # Assign group to user
#                     group_name = 'Member'
#                     group = Group.objects.get(name=group_name)
#                     user.groups.add(group)

#                     # Assign tenant to user upon registration
#                     form2.instance.tenant = tenant

#                     member = form2.save(commit=False)
#                     member.user = user

#                     member.save()

#                     # redirect to login page after successful registration
#                     return redirect('login', tenant_id = tenant_id)
#                 else:
#                     return HttpResponse('Your details do not match any of our records')

#             # Handle cases where there is no Scheme or Bad request
#             except requests.RequestException as e:
#                 return HttpResponse(f'Error contacting external server:{e}')
#         else:
#             errors = form1.errors.as_json() + form2.errors.as_json()
#             return HttpResponse(f'Some fields are invalid: {errors}')
#     else:
#         form1 = UserForm()
#         form2 = MemberForm()

#     return render(request, 'register.html', {'form1': form1, 'form2': form2})


@unauthenticated_user
def loginView(request, tenant_id):

    tenant = request.tenant

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password,tenant=tenant)

        if user is not None:
            # Redirect anyone with admin priviledge
            if user.groups.filter(name='Admin').exists():
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


class VerifyLoginOTPView(TemplateView):
    template_name = 'verify_otp.html'

    def get_user(self,user_id,tenant):
        return get_object_or_404(get_user_model(),id=user_id,tenant=tenant)

    def post(self,request,*args,**kwargs):
        tenant = self.request.tenant
        user_id = self.args.user_id
        user_email = self.args.user_email
        generated_otp = self.args.otp

        # Get OTP code
        otp_1 = request.POST.get('otp-1', '')
        otp_2 = request.POST.get('otp-2', '')
        otp_3 = request.POST.get('otp-3', '')
        otp_4 = request.POST.get('otp-4', '')

        # convert to integer
        otp = int(otp_1+otp_2+otp_3+otp_4)

        user = self.get_user(user_id,tenant)

        if user and otp==int(generated_otp):
            # login user
            login(request,user)

            # Redirect user based on groups
            # Member groups -->
            if user.groups.filter(name='Member').exists():
                return JsonResponse({
                    'status':'success',
                    'redirect_url':self.get_member_group_success_url(user)
                })
            # Redirect users without Member group
            return JsonResponse({
                'status':'success',
                'redirect_url':self.get_success_url()
            })
    
    def get_member_group_success_url(self,user):
        tenant = self.request.tenant
        member_id = user.member.staff_id
        url = reverse('member_dashboard', kwargs={
            'tenant_id':tenant.id,
            'member_id':member_id
        })
        return url
    
    def get_success_url(self):
        tenant = self.request.tenant
        url = reverse('finance_page', kwargs={'tenant_id':tenant.id})
        return url
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['email'] = self.args.user_email
        return context
    
            

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
    template_name = 'member_contributions.html'
    paginate_by = 12  

    def dispatch(self, request, *args, **kwargs):
        member_id = kwargs.get('member_id')
        tenant = request.tenant
        member = request.user.member
        
        if member.staff_id != member_id:
            return redirect('member_dashboard', tenant_id=tenant.id, member_id=member.staff_id)
        
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        member_id = self.kwargs.get('member_id')
        selected_year = self.request.GET.get('year', datetime.now().year)
        tenant = self.request.tenant
        scheme_id = self.request.scheme_name

        member = StaffAPI.objects.filter(staff_number=member_id, investment_scheme__tenant=tenant).first()

        if not member or not tenant or not scheme_id:
            return Contribution.objects.none()

        # Filter contributions for the selected year
        member_contributions = Contribution.objects.filter(
            member=member,
            investment_scheme__id=scheme_id,
            investment_scheme__tenant=tenant,
            year=selected_year,
            approved_contribution=True
        )

        return member_contributions

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        member_id = self.kwargs.get('member_id')
        selected_year = self.request.GET.get('year', datetime.now().year)
        tenant = self.request.tenant
        scheme_id = self.request.scheme_name

        member = StaffAPI.objects.filter(staff_number=member_id, investment_scheme__tenant=tenant).first()
        if not member or not tenant or not scheme_id:
            context['contributions'] = []
            context['total_contributions'] = 0
            context['yearly_contributions'] = 0
            context['last_contribution_amount'] = 0
            context['last_contribution_date'] = None
            return context

        contributions = self.get_queryset()

        # Calculate Total Contributions (All Time)
        total_contributions = Contribution.objects.filter(
            member=member,
            investment_scheme__tenant=tenant,
            approved_contribution=True
        ).aggregate(Sum('total_contribution'))['total_contribution__sum'] or 0.00

        # Calculate Yearly Contributions (For Selected Year)
        yearly_contributions = contributions.aggregate(Sum('total_contribution'))['total_contribution__sum'] or 0.00

        # Get Last Contribution
        last_contribution = contributions.order_by('-contribution_date').first()
        last_contribution_amount = last_contribution.total_contribution if last_contribution else 0.00
        last_contribution_date = last_contribution.contribution_date if last_contribution else None

        # Prepare context
        context['contributions'] = contributions
        context['total_contributions'] = total_contributions
        context['yearly_contributions'] = yearly_contributions
        context['last_contribution_amount'] = last_contribution_amount
        context['last_contribution_date'] = last_contribution_date

        # Populate Year Selection Dropdown
        years = Contribution.objects.filter(member=member).values_list('year', flat=True).distinct()
        context['years'] = sorted(set(years), reverse=True)
        context['selected_year'] = str(selected_year)

        return context


logger = logging.getLogger(__name__)
@method_decorator(tenant_login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Member']), name='dispatch')
class CreateTransactionView(View):
    template_name = 'create_transaction.html'

    def get(self, request, *args, **kwargs):
        tenant = request.tenant
        schemes = InvestmentScheme.objects.filter(tenant=tenant,approved=True)
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
                scheme = InvestmentScheme.objects.get(tenant=tenant, id=scheme_id, approved=True)
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

                staff.contributions = F('contributions') + amount
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
    paginate_by = 10 # Ensures pagination works
    context_object_name = 'transactions'

    def get_queryset(self):
        tenant = self.request.tenant
        staff_id = self.kwargs.get('staff_id')

        # Get filter parameters
        scheme_id = self.request.GET.get('scheme_id')
        status = self.request.GET.get('status')
        transaction_type = self.request.GET.get('transaction_type')
        payment_method = self.request.GET.get('payment_method')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        sort_by = self.request.GET.get('sort', '-transaction_date')

        # Get staff object
        staff = get_object_or_404(StaffAPI, tenant=tenant, staff_number=staff_id)

        # Query Transactions (includes WithdrawalRequest transactions)
        transactions = Transaction.objects.filter(staff=staff, tenant=tenant)

        # Apply filters
        if scheme_id:
            transactions = transactions.filter(scheme__id=scheme_id)
        if status:
            transactions = transactions.filter(status=status)
        if transaction_type:
            transactions = transactions.filter(transaction_type=transaction_type)
        if payment_method:
            transactions = transactions.filter(payment_method=payment_method)
        if date_from:
            transactions = transactions.filter(transaction_date__gte=date_from)
        if date_to:
            transactions = transactions.filter(transaction_date__lte=date_to)

        # Sorting
        transactions = transactions.order_by(sort_by)
        return transactions

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        staff_id = self.kwargs.get('staff_id')

        try:
            staff = get_object_or_404(StaffAPI, tenant=tenant, staff_number=staff_id)
            context['schemes'] = staff.investment_scheme.all()
        except StaffAPI.DoesNotExist:
            context['error'] = 'No transaction data available for this user'

        return context




@method_decorator(tenant_login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Member']), name='dispatch')
class WithdrawalView(TemplateView):
    template_name = 'withdrawal.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        context["schemes"] = InvestmentScheme.objects.filter(tenant=tenant, approved=True)
        return context
    
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            tenant = request.tenant
            member = request.user.member
            scheme_id = data.get('scheme_id')
            amount = data.get('amount')

            #  Validate inputs
            if not all([scheme_id, amount, member]):
                return JsonResponse({'status': 'error', 'message': 'Missing required fields.'}, status=400)

            amount = Decimal(amount)

            with transaction.atomic():
                #  Validate scheme and staff
                scheme = InvestmentScheme.objects.filter(tenant=tenant, id=scheme_id, approved=True).first()
                staff = StaffAPI.objects.filter(staff_number=member.staff_id).first()

                if not scheme or not staff:
                    return JsonResponse({'status': 'error', 'message': 'Invalid scheme or staff information.'}, status=400)

                # Create a withdrawal request
                withdrawal_request = WithdrawalRequest.objects.create(
                    tenant=tenant,
                    staff=staff,
                    scheme=scheme,
                    amount=amount,
                    request_date=timezone.now(),
                )
                logger.info(f" WithdrawalRequest created with ID: {withdrawal_request.id}")

                # Get all recipients for `withdrawal_request` event
                recipients = TenantEventNotification.objects.filter(
                    tenant=tenant,
                    event="withdrawal_request"
                ).values_list('staff__email', flat=True)  # Get list of emails

                if not recipients:
                    logger.warning(f"No recipients assigned for withdrawal_request event in tenant {tenant.id}")

                # Trigger Celery task to notify approvers
                transaction.on_commit(lambda: notify_withdrawal_approval.delay(tenant.id, withdrawal_request.id))


                # Trigger Celery task to notify the user
                notify_user_email_sms.delay(
                    tenant_id=tenant.id,  
                    member_name=member.user.get_full_name(),
                    first_name=member.user.first_name,
                    last_name=member.user.last_name,
                    user_email=member.user.email,
                    tel_number=member.tel_number,
                    amount=amount,
                    scheme_name=scheme.name
                )

                return JsonResponse({
                    'status': 'success',
                    'message': 'Withdrawal request submitted for approval. Notifications sent to user and approvers.'
                })

        except Exception as e:
            logger.error(f"Unexpected error in WithdrawalView: {str(e)}")
            return JsonResponse({'status': 'error', 'message': 'An unexpected error occurred.'}, status=500)
        
        
@method_decorator(tenant_login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Member']), name='dispatch')
class GetBalanceView(View):
    def get(self, request, *args, **kwargs):
        scheme_id = self.kwargs["scheme_id"]
        staff_id = self.kwargs["staff_id"]
        tenant = self.request.tenant
        try:
            staff = StaffAPI.objects.get(staff_number=int(staff_id), tenant=tenant)
        except ObjectDoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Staff not found'}, status=404)
        print("tenant:",tenant)
       
        try:
        # Fetch the investment scheme
            scheme = InvestmentScheme.objects.get(id=scheme_id, tenant=tenant,approved=True)

        except ObjectDoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Investment scheme not found.'})
        
        except Exception as e:
            logger.error(f"Error in GetBalanceView: {str(e)}")
            return JsonResponse({'status': 'error', 'message': 'An error occured'})
        try:
        
            # Validate if the staff_id matches a valid Membership
            membership = Membership.objects.filter(
                tenant=tenant,
                scheme=scheme,
                staff=staff
            ).first()
            print("staff_id:",staff)
        except ObjectDoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Membership not found.'})
        
        except Exception as e:
            logger.error(f"Error in GetBalanceView: {str(e)}")
            return JsonResponse({'status': 'error', 'message': 'An error occured'})
        

        # Calculate the available balance
        available_balance = membership.total_earnings

        return JsonResponse({
            'status': 'success',
            'balance': Decimal(available_balance)
        })


    
