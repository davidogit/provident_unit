from django import forms
from .models import LoanApplication

class LoanForm(forms.ModelForm):
    class Meta:
        model = LoanApplication
        fields = (
            'amount_requested',
            'purpose',
            'tenure_months'
        )