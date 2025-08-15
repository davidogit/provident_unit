from django.db import models, transaction
from MultiScheme.models import InvestmentScheme
from Fund.generate_invoice import generate_short_alpha_numeric_id
from MultiScheme.models import Tenant
from contributions.models import StaffAPI
from Member.models import  WithdrawalBatch


# MEMBER WITHDRAWAL APPLICATION
class WithdrawalRequest(models.Model):
    id = models.CharField(
        max_length=12,
        primary_key=True,
        unique=True,
        editable=False
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=False,
        related_name='withdrawal_request'
    )
    scheme = models.ForeignKey(
        InvestmentScheme,
        on_delete=models.CASCADE,
        null=True,
        related_name='withdrawal_request'
    )
    staff = models.ForeignKey(
        StaffAPI,
        on_delete=models.CASCADE,
        null=False,
        related_name='withdrawal_request'
    )
    amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=False,
        blank=False
    )
    parent_batch = models.ForeignKey(
        WithdrawalBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='withdrawal_request'
    )
    first_approval = models.BooleanField(
        default=False
    )
    second_approval = models.BooleanField(
        default=False
    )
    third_approval = models.BooleanField(
        default=False
    )
    fourth_approval = models.BooleanField(
        default=False
    )
    request_date = models.DateTimeField(
        auto_now_add=True,
        null=True
    )
    appoval_date =  models.DateTimeField(
        null=True,
        blank=True
    )

    def __str__(self):
        return f'{self.id} - {self.amount} - {self.staff.staff_number}'
    
    def save(self,*args,**kwargs):
        if not self.id:
            self.id = generate_short_alpha_numeric_id(WithdrawalRequest)

            """
            create Transaction object
            """
            self.save()
            Transaction.objects.create(
                tenant=self.tenant,
                staff=self.staff,
                scheme=self.scheme,
                transaction_type='Withdrawal',
                amount=self.amount,
                withdrawal_request=self
            )
            return 
        return super().save(*args,**kwargs)

class Transaction(models.Model):
    id = models.CharField(
        max_length=12,
        primary_key=True,
        unique = True,
        editable=False
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null = True
    )
    staff = models.ForeignKey(
        StaffAPI,
        on_delete=models.CASCADE,
        null=True
    )
    scheme = models.ForeignKey(
        InvestmentScheme,
        on_delete= models.CASCADE,
        related_name ="transactions"
    )
    withdrawal_request =  models.ForeignKey(
        WithdrawalRequest,
        on_delete=models.CASCADE,
        null=True,
        related_name='transactions'
    )
    transaction_date = models.DateTimeField(
        auto_now_add=True,
        null=True,
        blank=True
    )
    DEPOSIT = 'Deposit'
    WITHDRAWAL = 'Withdrawal'
    transaction_type_choices = [
        (DEPOSIT, 'Deposit'),
        (WITHDRAWAL, 'Withdrawal'),
        ('Scheduled Payout','Scheduled Payout'),
        ('General Payout','General Payout')
    ]
    transaction_type = models.CharField(
        max_length=20,
        choices=transaction_type_choices,
        default=DEPOSIT
    )

    MOBILE_MONEY = 'Mobile Money'
    BANK_TRANSFER = 'Bank Transfer'
    payment_method_choices = [
        (MOBILE_MONEY, 'Mobile Money'),
        (BANK_TRANSFER, 'Bank Transfer'),
        ('cheque','Cheque')
    ]
    payment_method = models.CharField(
        max_length=20,
        choices=payment_method_choices,
        default=MOBILE_MONEY
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )
    reference = models.TextField(
        max_length=255,
        blank=True,
        null=True
    )
    STATUS_CHOICES = [
        ('pending','Pending'),
        ('failed','Failed'),
        ('completed','Completed')
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text='Current status of the transaction'
    )

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} on {self.transaction_date}"
    
    def save(self,*args,**kwargs):
        if not self.id:
            self.id = generate_short_alpha_numeric_id(Transaction)
        return super().save(*args,**kwargs)

    class Meta:
        indexes = [
            models.Index(fields=['transaction_date']),
            models.Index(fields=['status']),
        ]

