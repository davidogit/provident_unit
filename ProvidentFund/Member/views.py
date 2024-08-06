from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.core.mail import send_mail
from ProvidentFund.settings import EMAIL_HOST_USER
from django.contrib.auth.decorators import login_required
from Member.forms import UserForm, MemberForm
from .generate_otp import generate_unique_code
from smtplib import SMTPConnectError
from django.views.generic import TemplateView

# Importing custom decorators
from .decorators import unauthenticated_user

@unauthenticated_user
def registrationView(request):
    if request.method == 'POST':
        form1 = UserForm(request.POST)
        form2 = MemberForm(request.POST)

        if form1.is_valid() and form2.is_valid():
            user = form1.save(commit=False)
            cleaned_password = form1.cleaned_data['password']
            user.set_password(cleaned_password)
            user.save()

            member = form2.save(commit=False)
            member.user = user

            # Associate registering member with a tenant before saving
            tenant = request.tenant
            if tenant:
                member.tenant = tenant

            member.save()

            return redirect('login')
        else:
            errors = form1.errors.as_json() + form2.errors.as_json()
            return HttpResponse(f'Some fields are invalid: {errors}')
    else:
        form1 = UserForm()
        form2 = MemberForm()

    return render(request, 'register.html', {'form1': form1, 'form2': form2})


@unauthenticated_user
def loginView(request, tenant_id):
    request.tenant = tenant_id 
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user:
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
            except SMTPConnectError as e:
                print(f'SMTPConnectError: {e}')

            # Save OTP in session for later verification
            request.session['otp_token'] = otp
            request.session['username'] = username


            # send user email to verify_otp view
            request.session['email'] = user.email

            return redirect('verify_otp', tenant_id=tenant_id)
        else:
            return redirect('invalid_login_details', tenant_id=tenant_id)

    return render(request, 'login.html')


class InvalidLoginDetails(TemplateView):
    template_name = 'login_error.html'





def verifyOtpView(request, tenant_id):
    request.tenant = tenant_id
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
        username = request.session.get('username')


        if otp == int(session_otp):
            user = authenticate(request, username=username)
            if user:
                login(request, user)
                # Clear session data after successful login
                del request.session['otp_token']
                del request.session['username']
    
                return redirect('finance_page', tenant_id)
            else:
                return HttpResponse('Invalid login details')
        else:
            return HttpResponse('Invalid OTP')

    return render(request, 'verify_otp.html',{'email':user_email})


@login_required
def logoutView(request):
    logout(request)
    return redirect('login')


def terms_and_conditions_view(request):
    # Render the terms and conditions template
    return render(request, 'terms_and_conditions.html')