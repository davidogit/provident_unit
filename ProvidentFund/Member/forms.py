from django import forms
# from django.contrib.auth.models import User
from django.contrib.auth import get_user_model

from Member.models import Member

class MemberForm(forms.ModelForm):

    class Meta:
        model = Member
        fields = ('staff_id','tel_number')

class UserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    class Meta:
        # We use the get_user_model instead of referencing the model directly
        model = get_user_model()
        fields = ('username','first_name','last_name','email','password')