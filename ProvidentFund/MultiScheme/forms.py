from django import forms
from . models import InvestmentScheme
class SchemeCreationForm(forms.ModelForm):
    class Meta:
        model = InvestmentScheme
        fields = (
            'code',
            'name',
            'distribution_percentage',
            'eligibility_criteria_months',
            'administrative_costs_percentage',
            'description',
        )
