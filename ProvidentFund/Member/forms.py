from django import forms
from .models import Member
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from .models import Member

class CombinedProfileForm(forms.ModelForm):
    # username = forms.CharField(required=True)
    # email = forms.EmailField(required=True)
    # Add other User model fields if necessary

    class Meta:
        model = Member
        fields = ['tel_number', 'address', 'nationality', 'image', 'marital_status', 'employment_date', 'department', 'job_title', 'scheme_approval']

        widgets = {
            'tel_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'employment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'nationality': forms.TextInput(attrs={'class': 'form-control'}),
            'marital_status': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'job_title': forms.TextInput(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={'class': 'form-control-file'}),
        }




class MemberForm(forms.ModelForm):

    class Meta:
        model = Member
        fields = ('staff_id','tel_number')

class UserForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')