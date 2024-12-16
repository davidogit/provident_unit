from django.db import models
from django.conf import settings
from MultiScheme.models import Tenant,InvestmentScheme
from django.db.models import UniqueConstraint
# Create your models here.

class ChartOfAccounts(models.Model):
    ACCOUNT_TYPES =[
        ('ASSET', 'Asset'),
        ('REVENUE', 'Revenue'),
        ('CAPITAL', 'Capital'),
        ('EXPENSE', 'Expense'),
        ('LIABILITY', 'Liability'),
    ]
    ACCOUNT_STATUS =[
        ('ACTIVE','Active'),
        ('CLOSED','Closed')
    ]
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        blank=False,
        related_name='chart_of_accounts'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='children'
    )
    name = models.CharField(
        max_length=255
    )
    description = models.TextField(
        null=True,
        blank=True
    )
    account_type = models.CharField(
        max_length=11,
        choices=ACCOUNT_TYPES,
        null=False,
        blank=False
    )
    account_status = models.CharField(
        max_length=20,
        choices=ACCOUNT_STATUS,
        null=True,
        blank=True,
        default=''
    )
    account_code = models.CharField(
        max_length=20,
        unique=True,
        null=False
    )
    current_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = 'Chart of Account'
        verbose_name_plural = 'Chart of Accounts'
        ordering = ['account_code']
    
    def __str__(self):
        return f'{self.account_code} - {self.name}'
    
    # We can use this to get the hierarchy  of an instance
    def get_hierarchy(self):
        hierarchy = []
        parent = self.parent

        while parent:
            hierarchy.append(parent)
            parent = parent.parent
        return reversed(hierarchy) #returns a top-down tree of account tree

from django.core.exceptions import ValidationError
class AccountMapping(models.Model):
    ACTIONS = [
        ('Contribution','Contribution'),
        ('Investment','Investment'),
        ('Earned Revenue','Earned Revenue'),
        ('Approved Revenue','Approved Revenue'),
        ('Delayed Interest','Delayed Interest'),
        ('Approved Delayed Interest','Approved Delayed Interest'),
        ('Benefit Payout','Benefit Payout'),
        ('Benefit Accrued','Benefit Accrued'),
        ('Exit Payout','Exit Payout'),
        ('Redeem Investment','Redeem Investment'),
        ('Investment Roll Over','Investment Roll Over')
    ]
    name = models.CharField(
        max_length=255,
        choices=ACTIONS,
        default=''
    )
    debit_acc = models.ForeignKey(
        ChartOfAccounts,
        on_delete=models.CASCADE,
        related_name='debit_mapping'
    )
    credit_acc = models.ForeignKey(
        ChartOfAccounts,
        on_delete=models.CASCADE,
        related_name='credit_mapping'
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    scheme = models.ForeignKey(
        InvestmentScheme,
        on_delete=models.CASCADE,
        null=True,
        blank= True
    )
    created_on = models.DateTimeField(auto_now_add=True,null=True)
    updated_on = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # Prevent duplicate events for a single tenant
    class Meta:
        constraints = [
            UniqueConstraint(fields=['tenant','name'], name='unique_name_per_tenant')
        ]


    def clean(self):
        if self.debit_acc == self.credit_acc:
            raise ValidationError('Debits and Credits account cannot be the same')
        
    def save(self,*args,**kwargs):
        self.clean()
        super().save(*args,**kwargs)