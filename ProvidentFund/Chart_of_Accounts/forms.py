from django import forms
from Chart_of_Accounts.models import ChartOfAccounts,AccountParameters

class ChartOfAccountsForm(forms.ModelForm):
    class Meta:
        model = ChartOfAccounts
        fields = ('__all__')

class AccountParameterForm(forms.ModelForm):
    class Meta:
        model = AccountParameters
        fields = ('account_code_length',)
