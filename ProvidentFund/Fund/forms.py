from django import forms
from . models import InvestmentDetail

# Create forms here

class InvestmentUpdateForm(forms.ModelForm):
    class Mets:
        model = InvestmentDetail
        fields = ('investment_type','account_name','account_type','account_number','principal_amount','interest_amount','interest_start_date','interest_end_date','interest_percentage')