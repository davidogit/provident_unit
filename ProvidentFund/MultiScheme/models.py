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
from django.conf import settings
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
    id = models.AutoField(
        primary_key=True,
        editable=False,
        unique=True
    )
    code = models.CharField(
        max_length=3,
        default=''
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE, related_name='investment_schemes',
        null=True
    )
    name = models.CharField(
        max_length=50,
        null=True
    )
    Yes = 'Yes'
    No = 'No'
    options = [
        (Yes,'Yes'),
        (No, 'No')
    ]
    delayed_int = models.CharField(
        max_length=3,
        choices=options,
        default=No,
        null=True
    )
    bank_int = models.CharField(
        max_length=3,
        choices=options,
        default=No,
        null=True
    )
    distribution_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        null=True
    )
    eligibility_criteria_months = models.IntegerField(
        null=True
    )
    description = models.TextField(
        blank=True, null=True
    )
    created_date = models.DateTimeField(
        auto_now_add=True
    )
    updated_date = models.DateTimeField(
        auto_now=True
    )
    administrative_costs_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        null=True
    )
    approved = models.BooleanField(
        default=False
    )

    def __str__(self):
        return f'{self.code} - {self.name}'
    

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
        help_text="Day of the month for contributions (1-31).",
        null=True
    )
    grace_period_contribution = models.PositiveSmallIntegerField( 
        validators=[MinValueValidator(0), MaxValueValidator(31)],
        help_text="Grace period for contributions in days.",
        null=True
    )
    delayed_interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Delayed interest rate as a percentage (0-100).",
        null=True
    )
    period_of_delayed_calculation = models.PositiveIntegerField(
        help_text="Period over which DI interest is to be calculated.",
        null=True
    ) #period over which interest is to be calculated.
    

    def __str__(self):
        return f"Settings for {self.investment_scheme.name}"

    class Meta:
        verbose_name = "Scheme Setting"
        verbose_name_plural = "Scheme Settings"


# Emails for sending Notifications and approval messages
class TenantEventNotification(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='tenant_event_notification',
        null=False
    )
    choice = [
        ('upcoming_payment_reminder','upcoming payment reminder'),
        ('scheduled_payment_date_approval','scheduled payment date approval'),
        ('general_payment_approval','general payment approval'),
        ('matured_investment_approval','approve matured investments'),
        ('approve_requisition','approve requisition'),
        ('withdrawal_first_approval','first level approval of withdrawal request'),
        ('withdrawal_second_approval','second level approval of withdrawal request'),
        ('withdrawal_third_approval','third level approval of withdrawal request'),
        ('approve_scheduled_date','approve scheduled date'),
    ]
    event = models.CharField(
        max_length=255,
        default='',
        choices=choice,
        null=False
    )
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    date_assigned = models.DateTimeField(
        auto_now_add=True,
        null=True
    )