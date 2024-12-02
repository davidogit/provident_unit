import json
from typing import Iterable
from django.db import models
# from Fund.models import AuditTrail
from django.db.models.signals import pre_delete,post_save
from django.utils.encoding import force_str
# from Fund.middleware import get_current_user
from django.utils import timezone
from django.dispatch import receiver
from django.core.validators import MinValueValidator,MaxValueValidator
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
    delayed_int = models.CharField(max_length=3, choices=options,default=No,null=True)
    bank_int = models.CharField(max_length=3, choices=options, default=No,null=True)

    # Daily = 'Daily'
    # Weekly = 'Weekly'
    # Monthly = 'Monthly'
    # frequency = [
    #     (Daily,'Daiily'),
    #     (Weekly,'Weekly'),
    #     (Monthly,'Monthly')
    # ]
    # contribution_frequency = models.CharField(max_length=20,choices=frequency,default='',null=True)
    # contribution_time = models.TimeField(null=True)
    # contribution_date = models.IntegerField(null=True, blank=True)

    # distribution_frequency = models.CharField(max_length=20, choices=frequency,default='', null=True)
    distribution_percentage = models.FloatField(null=True)
    eligibility_criteria_months = models.IntegerField(null=True)

    # every_six_months = '6 months'
    # every_year = '12 months'
    # every_eighteen_months = '18 months'
    # every_two_years = '24 months'
    # choices =[
    #     (every_six_months,'6 months'),
    #     (every_year, '12 months'),
    #     (every_eighteen_months, '18 months'),
    #     (every_two_years, '24 months')
    # ]
    # payout_frequency = models.CharField(max_length=20,choices=choices,default='', null=True)

    description = models.TextField(blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    administrative_costs_percentage = models.FloatField(null=True)

    # HISTORY
    # history = HistoricalRecords()

    def __str__(self):
        return f'{self.name} Scheme'
    

# Signals for StaffAPI
# @receiver(post_save, sender=InvestmentScheme)
# def audit_log_save(sender,instance,created,update_fields,**kwargs):
#     object_id = instance.pk

#     action = 'created' if created else 'updated'

#     # User making the change
#     user = get_current_user() or None
#     # Assign name 
#     if created:
#         instance.name = user.username
#         instance.save()

#     # Get changes to model
#     changes = {}

#     for field in instance._meta.fields:
#         field_name = field.name
#         new_value = getattr(instance,field_name)
#         changes[field_name] = force_str(new_value)
    
    

#     # Create an AuditTrail instance
#     AuditTrail.objects.create(
#         user = user,
#         model_name = InvestmentScheme.__name__,
#         action = action,
#         object_id = object_id,
#         changes = json.dumps(changes),
#         timestamp = timezone.now(),
#         name = user.username
#     )

# @receiver(pre_delete, sender=InvestmentScheme)
# def audit_log_delete(sender,instance,**kwargs):
#     object_id = instance.pk

#     action = 'deleted'

#     user = get_current_user() 

#     # Create an AuditTrail instance
#     AuditTrail.objects.create(
#         user = user,
#         model_name = InvestmentScheme.__name__,
#         action = action,
#         object_id = object_id,
#         changes = f'User {user.username} made a delete operation at {timezone.now()}',
#         timestamp = timezone.now(),
#         name = user.username
#     )


class SchemeSettings(models.Model):
    investment_scheme = models.OneToOneField(
        'InvestmentScheme', 
        on_delete=models.CASCADE, 
        related_name='scheme_settings'
    )
    contribution_day = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        help_text="Day of the month for contributions (1-31)."
    )
    grace_period_contribution = models.PositiveSmallIntegerField(
        default=0, 
        validators=[MinValueValidator(0), MaxValueValidator(31)],
        help_text="Grace period for contributions in days."
    )
    # grace_period_delayed_int = models.PositiveSmallIntegerField(
    #     default=0,
    #     validators=[MinValueValidator(0), MaxValueValidator(31)],
    #     help_text="Grace period for delayed interest in days."
    # )# Interest accumulation begins immediately after creating
    # daily_d_int_rate = models.DecimalField(
    #     max_digits=5, 
    #     decimal_places=4,
    #     validators=[MinValueValidator(0), MaxValueValidator(100)],
    #     help_text="Daily delayed interest rate as a percentage (0-100)."
    # )#we use same rate on delayed interest object
    delayed_interest_rate = models.FloatField( 
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Delayed interest rate as a percentage (0-100)."
    )
    period_of_delayed_calculation = models.PositiveIntegerField(
        help_text="Period over which DI interest is to be calculated."
    ) #period over which interest is to be calculated.
    

    def __str__(self):
        return f"Settings for {self.investment_scheme.name}"

    class Meta:
        verbose_name = "Scheme Setting"
        verbose_name_plural = "Scheme Settings"
