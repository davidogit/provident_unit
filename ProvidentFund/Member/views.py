from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.contrib.auth import login,authenticate
# Create your views here.





# class LoginView(TemplateView):
#     template_name= 'signin.html'

class LoginTemplateView(TemplateView):
    template_name = 'files/base.html'

# Importing Registration Forms

from Member.forms import UserForm,MemberForm



def registrationView(request):
    if request.method == 'POST':
        form1 = UserForm(request.POST)
        form2 = MemberForm(request.POST)

        if form1.is_valid() and form2.is_valid:

            form1.save(commit=False)
            cleaned_password = form1.cleaned_data['password']
            form1.set_password(cleaned_password)

            form1.save()

            form2.user = form1
            form2.save()

        else:
            return HttpResponse('Some fields are invalid')
    
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

        else:
            return HttpResponse('invalid login details')

    return render(request, 'login.hrml')