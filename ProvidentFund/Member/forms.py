from django import forms
# from django.contrib.auth.models import User
from django.contrib.auth import get_user_model

from .models import Member

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



from .models import Member

class MemberProfileForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = [
            'tel_number', 'address', 'date_of_birth', 'nationality',
            'image', 'marital_status', 'gender', 'employment_date',
            'department', 'job_title'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date','class':'form-control'}),
            'employment_date': forms.DateInput(attrs={'type': 'date','class':'form-control'}),
            'image': forms.FileInput(attrs={'class':'form-control-file'}),
            'tel_number': forms.TextInput(attrs={'class':'form-control'}),
            'address': forms.TextInput(attrs={'class':'form-control'}),
            'nationality': forms.TextInput(attrs={'class':'form-control'}),
            'marital_status': forms.TextInput(attrs={'class':'form-control'}),
            'gender': forms.Select(attrs={'class':'form-control'}),
            'department': forms.TextInput(attrs={'class':'form-control'}),
            'job_title': forms.TextInput(attrs={'class':'form-control'}),
        }
