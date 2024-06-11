from django import forms
from django.contrib.auth.models import User

from Member.models import Member

class MemberForm(forms.ModelForm):

    class Meta:
        model = Member
        fields = ('staff_id','tel_number')

class UserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    class Meta:
        model = User
        fields = ('username','first_name','last_name','email','password')