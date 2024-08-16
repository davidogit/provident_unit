from django.db import models
import uuid

# Create your models here.

# Tenanat model

class Tenant(models.Model):
    id = models.AutoField(primary_key=True, editable=False)
    name =  models.CharField(max_length=50, null=True, blank=True)
    api_endpoint_member = models.URLField(null=True)
    api_endpoint_contribution = models.URLField(null=True)
    tel_number =models.IntegerField(null=True)
    email = models.EmailField(null=True)
    address = models.CharField(max_length=100, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name}\'s Account'


# Schemes model

class InvestmentScheme(models.Model):
    id = models.AutoField(primary_key=True, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='investment_schemes',null=True)
    name = models.CharField(max_length=50,null=True)
    Yes = 'Yes'
    No = 'No'
    options = [
        (Yes,'Yes'),
        (No, 'No')
    ]
    delayed_int = models.CharField(max_length=3, choices=options,default=No)
    bank_int = models.CharField(max_length=3, choices=options, default=No)

    Daily = 'Daily'
    Weekly = 'Weekly'
    Monthly = 'Monthly'
    frequency = [
        (Daily,'Daiily'),
        (Weekly,'Weekly'),
        (Monthly,'Monthly')
    ]
    # contribution_frequency = models.CharField(max_length=20,choices=frequency,default='',null=True)
    contribution_time = models.TimeField(null=True)
    contribution_date = models.IntegerField(null=True)

    distribution_frequency = models.CharField(max_length=20, choices=frequency,default='', null=True)
    distribution_percentage = models.FloatField(null=True)
    eligibility_criteria_months = models.IntegerField(null=True)

    every_six_months = '6 months'
    every_year = '12 months'
    every_eighteen_months = '18 months'
    every_two_years = '24 months'
    choices =[
        (every_six_months,'6 months'),
        (every_year, '12 months'),
        (every_eighteen_months, '18 months'),
        (every_two_years, '24 months')
    ]
    payout_frequency = models.CharField(max_length=20,choices=choices,default='', null=True)
    description = models.TextField(blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)


    def __str__(self):
        return f'{self.name} Scheme'