from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.core.mail import send_mail
from ProvidentFund.settings import EMAIL_HOST_USER
from django.contrib.auth.decorators import login_required
from Member.forms import UserForm, MemberForm
from .models import Member
from .generate_otp import generate_unique_code

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
            member.save()

            return redirect('login')
        else:
            errors = form1.errors.as_json() + form2.errors.as_json()
            return HttpResponse(f'Some fields are invalid: {errors}')
    else:
        form1 = UserForm()
        form2 = MemberForm()

    return render(request, 'register.html', {'form1': form1, 'form2': form2})

def loginView(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user:
            # Generate OTP
            otp = generate_unique_code()

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
            request.session['password'] = password

            return redirect('verify_otp')
        else:
            return HttpResponse('Invalid login details')

    return render(request, 'login.html')

def verifyOtpView(request):
    if request.method == 'POST':
        otp = request.POST.get('otp')
 
        # Retrieve OTP from session
        session_otp = request.session.get('otp_token')
        username = request.session.get('username')
        password = request.session.get('password')

        if otp == session_otp:
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                # Clear session data after successful login
                del request.session['otp_token']
                del request.session['username']
                del request.session['password']
                return redirect('finance_page')
            else:
                return HttpResponse('Invalid login details')
        else:
            return HttpResponse('Invalid OTP')

    return render(request, 'verify_otp.html')

@login_required
def logoutView(request):
    logout(request)
    return redirect('login')


def terms_and_conditions_view(request):
    # Render the terms and conditions template
    return render(request, 'terms_and_conditions.html')