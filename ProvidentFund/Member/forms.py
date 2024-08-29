from django import forms
from .models import Member
from Admin.models import User
from django.contrib.auth import get_user_model
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
    
    # Setting username and email upon class intialization
    # def __init__(self, *args, **kwargs):
    #     user_instance = kwargs.pop('user_instance', None)
    #     super().__init__(*args, **kwargs)

    #     if user_instance:
    #         self.fields['username'].initial = user_instance.username
    #         self.fields['email'].initial = user_instance.email
    #         # Initialize other User fields if needed

    # def save(self, commit=True):
    #     member = super().save(commit=False)
    #     user = User.objects.get(pk=self.instance.user.pk)  # Assuming `user` is related to `Member`

    #     # Update user instance
    #     user.username = self.cleaned_data['username']
    #     user.email = self.cleaned_data['email']
    #     # Save other User fields if necessary

    #     if commit:
    #         user.save()
    #         member.save()

    #     return member





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