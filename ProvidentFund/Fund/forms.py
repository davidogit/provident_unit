from django import forms
from . models import InvestmentDetail

# Create forms here

class InvestmentUpdateForm(forms.ModelForm):
    class Meta:
        model = InvestmentDetail
        fields = ('investment_type','account_name','account_type','account_number','principal_amount','interest_start_date','interest_end_date','interest_percentage')

        widgets = {
            'investment_type': forms.Select(attrs={'class': 'form-control'}),
            'account_name': forms.TextInput(attrs={'class': 'form-control'}),
            'account_type': forms.Select(attrs={'class': 'form-control'}),
            'account_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'principal_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'interest_start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'interest_end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'interest_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }