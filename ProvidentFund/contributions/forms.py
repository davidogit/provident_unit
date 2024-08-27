from django import forms
from Member.models import Member

class MemberProfileForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = [
            'tel_number', 'address', 'date_of_birth', 'nationality',
            'image', 'marital_status', 'gender', 'employment_date',
            'department', 'job_title'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'employment_date': forms.DateInput(attrs={'type': 'date'}),
        }
