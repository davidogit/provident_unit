from django import forms
from .models import SchemeSettings

class SchemeSettingsForm(forms.ModelForm):
    class Meta:
        model = SchemeSettings
        firlds = ('contribution_day','grace_period_contribution','grace_period_delayed_int','daily_d_int_rate','delayed_interest_rate')
