from django.shortcuts import render
from django.views.generic import TemplateView
# Create your views here.





class LoginView(TemplateView):
    template_name= 'signin.html'

class LoginTemplateView(TemplateView):
    template_name = 'signin.html' 