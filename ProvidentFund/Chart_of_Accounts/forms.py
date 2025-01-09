from django import forms
from Chart_of_Accounts.models import ChartOfAccounts

class ChartOfAccountsForm(forms.ModelForm):
    class Meta:
        model = ChartOfAccounts
        fields = ('__all__')
