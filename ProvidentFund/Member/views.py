from django.contrib.auth import authenticate, login, logout
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse
from django.core.mail import send_mail
from django.urls import reverse, reverse_lazy
from ProvidentFund.settings import EMAIL_HOST_USER
from django.contrib.auth.decorators import login_required
from Member.forms import UserForm, MemberForm
from .generate_otp import generate_unique_code
from smtplib import SMTPConnectError
from django.views.generic import TemplateView,CreateView
from django.contrib.auth.models import Group

from MultiScheme.models import Tenant
# Importing the user model 
from django.contrib.auth import get_user_model

# Importing custom decorators
from .decorators import unauthenticated_user

@unauthenticated_user
def registrationView(request,tenant_id):
    if request.method == 'POST':
        form1 = UserForm(request.POST)
        form2 = MemberForm(request.POST)

        if form1.is_valid() and form2.is_valid():

            # Assign tenant to user upon registration
            tenant = Tenant.objects.get(id=tenant_id)
            form1.instance.tenant = tenant

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
            errors = form1.errors.as_json() + form2.errors.as_json()
            return HttpResponse(f'Some fields are invalid: {errors}')
    else:
        form1 = UserForm()
        form2 = MemberForm()

    return render(request, 'register.html', {'form1': form1, 'form2': form2})


@unauthenticated_user
def loginView(request, tenant_id):
    # print(tenant_id)
    tenant = Tenant.objects.get(id=tenant_id)
    # request.tenant = tenant_id 
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password,tenant=tenant)

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
        otp_1 = request.POST.get('otp-1')
        otp_2 = request.POST.get('otp-2')
        otp_3 = request.POST.get('otp-3')
        otp_4 = request.POST.get('otp-4')

        # concantenate otp
        otp_combined = otp_1+otp_2+otp_3+otp_4
        # convert otp from string to integer
        otp = int(otp_combined)

        # Retrieve OTP from session
        session_otp = request.session.get('otp_token')
        # username = request.session.get('username')


        if otp == int(session_otp):
            # we manually set the auth backend to our backend so it can authenticate based on the tenant
            user.backend = 'Member.backends.TenantAwareBackend'
            login(request, user)
            # Clear session data after successful login
            del request.session['otp_token']
            # del request.session['username']

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