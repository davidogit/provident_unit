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


class Contribution(models.Model):
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
    
    def save(self, *args, **kwargs):
        """
        Optimized save method that incrementally updates member contributions
        instead of recalculating from scratch every time
        """
        from decimal import Decimal
        
        # Extract month and year from the contribution_date
        if self.contribution_date:
            self.month = str(self.contribution_date.month)
            self.year = str(self.contribution_date.year)
        
        # Convert all amounts to Decimal before arithmetic
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

        # Check if this is a new object or an update
        is_new = self.pk is None
        
        # Get old values for comparison if this is an update
        old_total = Decimal('0.00')
        old_approved = False
        
        if not is_new:
            try:
                old_contribution = Contribution.objects.get(pk=self.pk)
                old_total = old_contribution.total_contribution or Decimal('0.00')
                old_approved = old_contribution.approved_contribution
            except Contribution.DoesNotExist:
                # Handle edge case where object doesn't exist
                is_new = True

        # Save the main object first
        super().save(*args, **kwargs)

        # OPTIMIZED: Incrementally update member contributions
        if self.member:
            # Get current contributions (handle None case)
            current_contributions = self.member.contributions or Decimal('0.00')
            new_total = self.total_contribution or Decimal('0.00')
            
            if is_new:
                # New contribution - add if approved
                if self.approved_contribution:
                    current_contributions += new_total
            else:
                # Existing contribution - handle all change scenarios
                if old_approved and self.approved_contribution:
                    # Both old and new are approved - adjust by difference
                    difference = new_total - old_total
                    current_contributions += difference
                elif old_approved and not self.approved_contribution:
                    # Was approved, now not approved - subtract old amount
                    current_contributions -= old_total
                elif not old_approved and self.approved_contribution:
                    # Wasn't approved, now approved - add new amount
                    current_contributions += new_total
                # If both old and new are not approved, no change needed
            
            # Update member's contributions
            self.member.contributions = max(current_contributions, Decimal('0.00'))  # Ensure non-negative
            self.member.save(update_fields=['contributions'])


# Signal to handle contribution deletions
@receiver(pre_delete, sender=Contribution)
def update_member_contributions_on_delete(sender, instance, **kwargs):
    """
    Update member contributions when a contribution is deleted
    """
    if instance.member and instance.approved_contribution:
        current_contributions = instance.member.contributions or Decimal('0.00')
        contribution_amount = instance.total_contribution or Decimal('0.00')
        
        # Subtract the deleted contribution
        new_contributions = current_contributions - contribution_amount
        instance.member.contributions = max(new_contributions, Decimal('0.00'))  # Ensure non-negative
        instance.member.save(update_fields=['contributions'])


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
    
    def save(self, *args, **kwargs):
        """
        Optimized save method that incrementally updates staff amounts
        """
        # Check if this is a new object or an update
        is_new = self.pk is None
        
        # Get old values for comparison if this is an update
        old_total_earnings = Decimal('0.00')
        old_estimated_profit = Decimal('0.00')
        
        if not is_new:
            try:
                old_membership = Membership.objects.get(pk=self.pk)
                old_total_earnings = old_membership.total_earnings or Decimal('0.00')
                old_estimated_profit = old_membership.estimated_profit or Decimal('0.00')
            except Membership.DoesNotExist:
                is_new = True
        
        # Save membership first
        super().save(*args, **kwargs)
        
        # OPTIMIZED: Incrementally update staff amounts
        current_actual_amount = self.staff.actual_amount or Decimal('0.00')
        current_estimated_profit = self.staff.estimated_profit or Decimal('0.00')
        
        new_total_earnings = self.total_earnings or Decimal('0.00')
        new_estimated_profit = self.estimated_profit or Decimal('0.00')
        
        if is_new:
            # New membership - add amounts
            current_actual_amount += new_total_earnings
            current_estimated_profit += new_estimated_profit
        else:
            # Existing membership - adjust by differences
            earnings_difference = new_total_earnings - old_total_earnings
            profit_difference = new_estimated_profit - old_estimated_profit
            
            current_actual_amount += earnings_difference
            current_estimated_profit += profit_difference
        
        # Update staff fields
        self.staff.actual_amount = max(current_actual_amount, Decimal('0.00'))
        self.staff.estimated_profit = max(current_estimated_profit, Decimal('0.00'))
        self.staff.save(update_fields=['actual_amount', 'estimated_profit'])


# Signal to handle membership deletions
@receiver(pre_delete, sender=Membership)
def update_staff_amounts_on_delete(sender, instance, **kwargs):
    """
    Update staff amounts when a membership is deleted
    """
    current_actual_amount = instance.staff.actual_amount or Decimal('0.00')
    current_estimated_profit = instance.staff.estimated_profit or Decimal('0.00')
    
    membership_earnings = instance.total_earnings or Decimal('0.00')
    membership_profit = instance.estimated_profit or Decimal('0.00')
    
    # Subtract the deleted membership amounts
    new_actual_amount = current_actual_amount - membership_earnings
    new_estimated_profit = current_estimated_profit - membership_profit
    
    instance.staff.actual_amount = max(new_actual_amount, Decimal('0.00'))
    instance.staff.estimated_profit = max(new_estimated_profit, Decimal('0.00'))
    instance.staff.save(update_fields=['actual_amount', 'estimated_profit'])