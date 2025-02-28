from django.db import models
from django.conf import settings
from MultiScheme.models import Tenant,InvestmentScheme
from django.db.models import UniqueConstraint
from django.core.exceptions import ValidationError

# Create your models here.

class ChartOfAccounts(models.Model):
    ACCOUNT_TYPES =[
        ('ASSET', 'ASSET'),
        ('REVENUE', 'REVENUE'),
        ('CAPITAL', 'CAPITAL'),
        ('EXPENSE', 'EXPENSE'),
        ('LIABILITY', 'LIABILITY'),
    ]
    ACCOUNT_STATUS =[
        ('ACTIVE','ACTIVE'),
        ('CLOSED','CLOSED')
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
        
        children = self.children.all()
        hierarchy =list(children)

        #referencing the related name on the parent field
        for child in children: 
            hierarchy.extend(child.get_hierarchy())

        return hierarchy #returns a down-top(child to highest parent) tree of account tree
    
    def calculate_total_balance(self):
        """
        calculates total balance for the account, including individual balance of its children
        """
        total_balance = self.current_balance
        # call hierachy on obj to return its 
        children = self.get_hierarchy()
        for child in children:
            total_balance += child.current_balance
        return total_balance

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
        ('Roll Over','Roll Over'),
        ('Supplier Invoice Creation','Supplier Invoice Creation'),
        ('Supplier Invoice Payment','Supplier Invoice Payment'),
        ('Member Withdrawal Invoice','Member Withdrawal Invoice'),
        ('Member Withdrawal Invoice Payment','Member Withdrawal Invoice Payment'),
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
        blank= True,
        related_name='account_mapping'
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
            UniqueConstraint(fields=['tenant','scheme','name'], name='unique_name_per_tenant')
        ]

    def __str__(self):
        return f'{self.tenant.name} - {self.scheme} - {self.name}'

    def clean(self):
        if self.debit_acc == self.credit_acc:
            raise ValidationError('Debits and Credits account cannot be the same')
        
    def save(self,*args,**kwargs):
        self.clean()
        super().save(*args,**kwargs)


class BankAccount(models.Model):
    CURRENCY = [
        ('GHS','GHS'),
        ('USD','USD'),
        ('EUR','EUR')
    ]
    ACCOUNT_TYPE = [
        ('current','Current'),
        ('checking','Checking'),
        ('savings','Savings'),
        ('fixed deposit','Fixed Deposit'),
        ('business','Business')
    ]
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='bank_accounts'
    )
    account_number = models.CharField(
        max_length=255
    )
    bank_name = models.CharField(
        max_length=255
    )
    account_holder_name = models.CharField(
        max_length=255
    )
    branch = models.CharField(
        max_length=255
    )
    account_type = models.CharField(
        max_length=255,
        choices=ACCOUNT_TYPE,
        default='business'
    )
    parent_Account = models.ForeignKey(
        ChartOfAccounts,
        on_delete=models.SET_NULL,
        related_name='bank_accounts',
        null=True
    )
    bank_email = models.EmailField(
        null=True,
        blank=False
    )
    currency = models.CharField(
        max_length=255,
        choices=CURRENCY,
        default='GHS'
    )

    def __str__(self):
        return f'{self.bank_name} | {self.branch} | {self.account_number}'