from django.db import models
from MultiScheme.models import InvestmentScheme,Tenant
from Fund.models import AuditTrail
from django.utils import timezone
import json
from django.db.models.signals import pre_delete,post_save
from django.dispatch import receiver
from django.utils.encoding import force_str
import logging
logger = logging.getLogger(__name__)
from Fund import middleware
from django.db.models import Sum
from decimal import Decimal

class StaffAPI(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        related_name='staff_api'
    )
    investment_scheme = models.ManyToManyField(
        InvestmentScheme,
        related_name='staff_api'
    )
    Id = models.AutoField(
        primary_key=True,
        unique=True,
        editable=False
    )
    first_name = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )
    last_name = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )
    staff_number = models.CharField(
        unique=True,
        max_length=20
    )
    date_joined = models.DateField(
        auto_now_add=True
    )
    status = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        default='active'
    )
    fund_type = models.CharField(
        max_length=50
    )
    contributions = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        default=0.00)#holds users accumulated contributions
    exited_date = models.DateField(
        null=True,
        blank=True
    )
    exited_flag = models.BooleanField(
        default=False
    )
    estimated_profit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    ) # Estimated interest to gain NB: does not include contributions
    actual_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    ) # holds recorgnised interest only
    subscription_date = models.DateField(
        null=True
    )
    updated_date = models.DateTimeField(
        auto_now=True
    )
    last_withdrawal_date = models.DateTimeField(
        null=True,
        blank=True
    )
    # New fields for bank details
    bank_name = models.CharField(
        max_length=255,
        default='',
        null=True,
        blank=True
    )
    bank_branch = models.CharField(
        max_length=255,
        default='',
        null=True,
        blank=True
    )
    bank_account_number = models.CharField(
        max_length=255,
        default='',
        null=True,
        blank=True
    )


    def __str__(self):
        return f'{self.last_name} {self.first_name}'
    
    @property
    def total_amount(self):
        return self.contributions+self.actual_amount
    
    # @property
    # def amount(self):
    #     return self._amount
    
    # @amount.setter
    # def amount(self,value):
    #     self._amount += value



# Signals for StaffAPI
# @receiver(post_save, sender=StaffAPI)
# def audit_log_save(sender,instance,created,update_fields,**kwargs):
#     from Fund.middleware import get_current_user

#     object_id = instance.pk

#     action = 'created' if created else 'updated'

#     # User making the change
#     # user = get_current_user() or None
#     user = middleware.get_current_user()
#     # Assign name 
#     if created:
#         instance.name = user
#         instance.save()

#     # Get changes to model
#     changes = {}

#     for field in instance._meta.fields:
#         field_name = field.name
#         new_value = getattr(instance,field_name)
#         changes[field_name] = force_str(new_value)
        
#     logger.info(f'User: {user}')
#     # Create an AuditTrail instance
#     AuditTrail.objects.create(
#         user = user,
#         model_name = StaffAPI.__name__,
#         action = action,
#         object_id = object_id,
#         changes = json.dumps(changes),
#         timestamp = timezone.now(),
#         name = user.username
#     )

# @receiver(pre_delete, sender=StaffAPI)
# def audit_log_delete(sender,instance,**kwargs):
#     from Fund.middleware import get_current_user
#     # current_user = CurrentUserMiddleware(None)
#     object_id = instance.pk

#     action = 'deleted'

#     user = get_current_user()
#     # get_object_or_404(get_user_model(),id=instance.pk)
    
#     # Create an AuditTrail instance
#     AuditTrail.objects.create(
#         user = user,
#         model_name = StaffAPI.__name__,
#         action = action,
#         object_id = object_id,
#         changes = f'User {user} made a delete operation at {timezone.now()}',
#         timestamp = timezone.now(),
#         name = user.username
#     )



class Contribution(models.Model):
    # tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True)
    investment_scheme = models.ForeignKey(
        InvestmentScheme,
        on_delete=models.CASCADE,
        null=True,
        related_name='contribution'
    )
    member = models.ForeignKey(
        StaffAPI,
        related_name='contribution' ,
        on_delete=models.CASCADE
    )
    month = models.CharField(
        max_length=20
    )
    year = models.CharField(
        max_length=4
    )
    employee_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )
    employer_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )
    retro_employee_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )
    retro_employer_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )
    contribution_date = models.DateField()
    approved_contribution = models.BooleanField(default=False)
    total_contribution = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.member.last_name}'s - {self.month} {self.year}"
    

    # Saving every contribution for user whenever a contribution is made
    def save(self, *args, **kwargs):
        """
        Saving every contribution for user whenever a contribution is made
        """
        from decimal import Decimal
        from django.db.models import Sum
    
    # Extract month and year from the contribution_date
        if self.contribution_date:
            self.month = str(self.contribution_date.month)
            self.year = str(self.contribution_date.year)
        
        # Convert all amounts to Decimal before arithmetic (FIXES THE DECIMAL+FLOAT ERROR)
        employee_amt = Decimal(str(self.employee_amount)) if self.employee_amount is not None else Decimal('0.00')
        employer_amt = Decimal(str(self.employer_amount)) if self.employer_amount is not None else Decimal('0.00')
        retro_employee_amt = Decimal(str(self.retro_employee_amount)) if self.retro_employee_amount is not None else Decimal('0.00')
        retro_employer_amt = Decimal(str(self.retro_employer_amount)) if self.retro_employer_amount is not None else Decimal('0.00')
        
        # Calculate sum of contribution using safe Decimal arithmetic
        self.total_contribution = (
            employee_amt +
            employer_amt +
            retro_employee_amt +
            retro_employer_amt
        )

        # Save the main object first to ensure total_contributions is saved
        super().save(*args, **kwargs)

        # FIXED: Update member.contributions (not member.amount which doesn't exist)
        if self.member:
            # Calculate total approved contributions for this member
            total_member_contributions = Contribution.objects.filter(
                member=self.member,
                approved_contribution=True
            ).aggregate(
                total=Sum('total_contribution')
            )['total'] or Decimal('0.00')
            
            # Update the member's contributions field
            self.member.contributions = total_member_contributions
            self.member.save(update_fields=['contributions'])


# MEMBERSHIP MODEL FOR STAFF
"""
This model is to track how many schemes a member
belongs to and it is unique by scheme and member hence 
a member can belong to one scheme once.

This allows to know how much a user has made from a
particular scheme... both total and estimated earnings
"""
class Membership(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=False,
        related_name='membership'
    )
    staff = models.ForeignKey(
        StaffAPI,
        on_delete=models.CASCADE,
        null=False,
        related_name='membership'
    )
    scheme = models.ForeignKey(
        InvestmentScheme,
        on_delete=models.CASCADE,
        null=False,
        related_name='membership'
    )
    total_earnings = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.0,
        null=True,
        blank=True,
    )
    estimated_profit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.0,
        null=True,
        blank=True
    )
    enrolled_at = models.DateField(
        auto_now_add=True,
        null=False,
        blank=False
    )

    class Meta:
        unique_together = ('staff','scheme') #Ensures staff can be enrolled once

    def __str__(self):
        return f'{self.staff.first_name} - Membership'
    
    # Update both membership and corresponding staff balances(total_amount)
    def save(self,*args,**kwargs):
        super().save(*args,**kwargs) #save membership update
        # Update the amount field on the parent StaffApi model to reflect change in amount
        total_earnings = Membership.objects.filter(
            staff=self.staff,
        ).aggregate(total=Sum('total_earnings'))['total'] or Decimal(0.0)

        estimated_profit = Membership.objects.filter(
            staff=self.staff,
        ).aggregate(total=Sum('estimated_profit'))['total'] or Decimal(0.0)
        self.staff.actual_amount = total_earnings
        self.staff.estimated_profit = estimated_profit
        # save staff update
        self.staff.save()
