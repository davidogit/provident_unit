from django import forms
from .models import LoanApplication, LoanType, LoanTopUp


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


class LoanTopUpRequestForm(forms.ModelForm):
    class Meta:
        model = LoanTopUp
        fields = ['topup_amount', 'new_tenure_months', 'note']

    def clean_topup_amount(self):
        amount = self.cleaned_data.get('topup_amount')
        if amount <= 0:
            raise forms.ValidationError("Top-up amount must be greater than zero.")
        return amount