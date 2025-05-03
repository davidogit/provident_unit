from django.db import models
from Member.models import Member
from django.conf import settings
from MultiScheme.models import Tenant
from decimal import Decimal
# Create your models here.

# Model for Loan tracking
class LoanApplication(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='loan_applications'
    )
    STATUS_CHOICES = [
        ('PENDING','Pending'),
        ('REJECTED','Rejected'),
        ('APPROVED','Approved'),
        ('DISBURSED','Disbursed'),
        ('REPAID','Repaid')
    ]
    
    user = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='loan_applications'
    )
    amount_requested = models.DecimalField(
        decimal_places=2,
        max_digits=12,
    )
    purpose = models.TextField()
    application_date = models.DateTimeField(
        auto_now_add=True
    )
    status = models.CharField(
        choices=STATUS_CHOICES,
        default='PENDING',
        max_length=10
    )
    application_date = models.DateTimeField(
        auto_now_add=True
    )
    approval_date = models.DateTimeField(
        null=True,
        blank=True
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='appproved_loans',
        null=True
    )
    disbursement_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Date loan was paid to Member.'
    )
    repayment_due_date = models.DateField(
        null=True,
        blank=True
    )
    interest_rate = models.DecimalField(
        decimal_places=2,
        max_digits=5,
        null=True
    )
    tenure_months = models.PositiveIntegerField(
        help_text='Duration over which loan is to be paid'
    )
    monthly_installments = models.DecimalField(
        decimal_places=2,
        max_digits=12,
        blank=True,
        null=True
    )

    def __str__(self):
        return f'Loan application - {self.user.user.username} - Amount- {self.amount_requested}.'
    
    def total_interest_flat(self):
        p = self.amount_requested
        r = self.interest_rate
        t_months = self.tenure_months
        t_years = t_months/12 #convert months to years

        return round((p*r*t_years)/100, 2)
    
    def loan_processing_fee_flat(self):
        # 1.5% of loan amount
        processing_fee = Decimal(self.amount_requested*(1.5/100))
        return processing_fee
    
    def disbursement_amount(self):

        return self.amount_requested - self.loan_processing_fee_flat()

    def total_payable_amount_flat(self):
        return round(self.amount_requested + self.total_interest_flat(), 2)

    def calculate_monthly_installments_flat(self):
        p = self.amount_requested
        r = self.interest_rate
        t_months = self.tenure_months
        t_years = Decimal(t_months/12) #convert months to years

        # Monthly installments using Equated Monthly Installments EMI
        total_interest = (p*r*t_years)/100

        total_amount_payable = total_interest+p

        monthly_emi = total_amount_payable/t_months

        return round(monthly_emi, 2) #round value to 2dp
    
    def save(self, *args, **kwargs):
        if self.amount_requested and self.interest_rate and self.tenure_months:
            self.monthly_installments = self.calculate_monthly_installments_flat()
        return super().save(*args,**kwargs)

