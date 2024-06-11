from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.contrib.auth import login,authenticate
from django.shortcuts import redirect
# Create your views here.





# class LoginView(TemplateView):
#     template_name= 'signin.html'

# class LoginTemplateView(TemplateView):
#     template_name = 'files/base.html'

# Importing Registration Forms

from Member.forms import UserForm,MemberForm



def registrationView(request):
    if request.method == 'POST':
        form1 = UserForm(request.POST)
        form2 = MemberForm(request.POST)

        if form1.is_valid() and form2.is_valid:

            user = form1.save(commit=False)
            cleaned_password = form1.cleaned_data['password']
            user.set_password(cleaned_password)

            user.save()

            member = form2.save(commit=False)
            member.user = user
            member.save()

            return redirect('login')

        else:
            # return HttpResponse('Some fields are invalid')
            errors = form1.errors.as_json() + form2.errors.as_json()
            return HttpResponse(f'Some fields are invalid: {errors}')
    
    else:
        form1 = UserForm()
        form2 = MemberForm()

    return render(request, 'register.html')



def loginView(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)

            return redirect('finance_page')

        else:
            return HttpResponse('invalid login details')

    return render(request, 'login.html')