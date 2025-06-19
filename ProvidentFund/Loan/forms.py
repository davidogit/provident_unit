from django import forms
from .models import LoanApplication,LoanType

class LoanForm(forms.ModelForm):
    class Meta:
        model = LoanApplication
        fields = (
            'amount_requested',
            'purpose',
            'tenure_months',
            'interest_rate',
            # 'loan_type'
        )


class LoanTypeForm(forms.ModelForm):
    class Meta:
        model = LoanType
        exclude = ['tenant','created_at']