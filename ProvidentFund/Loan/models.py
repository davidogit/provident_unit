from django.db import IntegrityError, models
from Member.models import Member
from django.conf import settings
from MultiScheme.models import Tenant
from decimal import Decimal,ROUND_HALF_UP
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import UniqueConstraint
"""
CHART OF ACCOUNTS IMPORT
"""
from Chart_of_Accounts.models import ChartOfAccounts
# Create your models here.

"""
LOAN-TYPE: This model is to help create different type
of loan offers to members
"""
class LoanType(models.Model):
    name = models.CharField(
        max_length=50
    )
    description = models.TextField(
        help_text='Optional description of this loan type: To be displayed to members when applying'
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=False,
        related_name='loan_types'
    )
    minimum_year = models.PositiveIntegerField(
        help_text='minimum number of years required to apply for a loan.'
    )
    minimum_contribution_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Minimum amount contributed to PF.'
    )
    requires_membership = models.BooleanField(
        default=True,
        help_text='Choose who to apply to this loan type: Enrolled members or all members'
    )
    min_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal(0),
        help_text='minimum loan amount allowed'
    )
    max_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='maximum loan amount allowed'
    )
    loan_interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal(0),
        help_text='Anual interest rate as percentage'
    )
    interest_calculation_type = models.CharField(
        max_length=8,
        choices=[('FLAT','flat'),('REDUCING','Reducing')], default='FLAT',
        help_text='Interest calculation type: Flat or Reducing balance'
    )
    loan_fee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text='Loan processing fee percentage. eg. 1.5 for 1.5\% \of loan amount'
    )
    late_payment_penalty = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text='Daily penalty for defaulters in percenrages. eg.1.5 for 1.5%'
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )


"""
LOAN APPLICATIONS-  Keeps track of all loan applications made
"""
# Model for Loan tracking
class LoanApplication(models.Model):
    loan_type = models.ForeignKey(
        LoanType,
        on_delete=models.DO_NOTHING,
        related_name='loan_applications',
        null=True
    )
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
    status = models.CharField(
        choices=STATUS_CHOICES,
        default='PENDING',
        max_length=10
    )
    application_date = models.DateTimeField(
        auto_now_add=True
    )
    approved = models.BooleanField(
        default=False
    )
    approval_date = models.DateTimeField(
        null=True,
        blank=True
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='approved_loans',
        null=True
    )
    disbursed = models.BooleanField(
        default=False
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
    total_amount_paid = models.DecimalField(
        decimal_places=2,
        max_digits=12,
        null=True,
        default=Decimal(0),
        help_text='to be calculated automatically when a payment is made'
    )

    def __str__(self):
        return f'Loan application - {self.user.user.username} - Amount- {self.amount_requested}.'
    

    """
    TOTAL INTEREST FLAT
    """
    def total_interest_flat(self):
        p = self.amount_requested
        r = self.loan_type.loan_interest_rate
        t_months = self.tenure_months
        t_years = t_months/Decimal('12') #convert months to years

        interest = (p*r*t_years)/Decimal('100')

        return interest.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    

    """
    PROCESSING FEE ON LOAN
    """
    def loan_processing_fee_flat(self):
        # 1.5% of loan amount
        fee_percentage_in_decimal = self.loan_type.loan_fee_percentage/Decimal('100')
        processing_fee = Decimal(self.amount_requested*fee_percentage_in_decimal)

        return processing_fee.quantize(Decimal("0.01"),rounding= ROUND_HALF_UP)
    

    """
    DISBURSEMENT AMOUNT
    """
    def disbursement_amount(self):
        return self.amount_requested - self.loan_processing_fee_flat()


    """
    TOTAL LOAN AMOUNT PAYABLE
    """
    def total_payable_amount_flat(self):
        return round(self.amount_requested + self.total_interest_flat(), 2)


    """
    CALCULATE MONTHLY FLAT INSTALLMENTS USING EMI(
            REDUCING BALANCE OR FLAT
        )
    """
    def calculate_monthly_installments(self):
        p = self.amount_requested
        annual_rate = self.loan_type.loan_interest_rate  # e.g., 6.5%
        r = Decimal(annual_rate) / Decimal('1200')  # Monthly interest rate
        T = Decimal(self.tenure_months)

        emi = Decimal('0.00')  # Default fallback

        if r == 0:
            emi = p / T
        else:
            if self.loan_type.interest_calculation_type == 'FLAT':
                # Total interest = P * R * T(years)
                total_interest = (p * Decimal(annual_rate) * (T / Decimal('12'))) / Decimal('100')
                total_payable = p + total_interest
                emi = total_payable / T

            elif self.loan_type.interest_calculation_type == 'REDUCING':
                # Reducing balance formula (standard EMI)
                numerator = p * r * (1 + r) ** T
                denominator = ((1 + r) ** T) - 1
                emi = numerator / denominator
            else:
                raise ValueError("Invalid interest calculation type.")

        return emi.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        
    """
    APPROVE LOAN -- BY ADMIN
    """ 
    def approve_loan(self, user):
        if self.approved == True:
            raise Exception("Loan already processed.")
        
        self.status = 'APPROVED'
        self.approved_by = user
        self.approved = True
        self.approval_date = timezone.now()
        self.save()
        
    

    """
    SAVE METHOD
    """
    def save(self, *args, **kwargs):
        # Calculate for only new loan applications
        if not self.pk:
            if self.amount_requested and self.loan_type and self.tenure_months:
                self.monthly_installments = self.calculate_monthly_installments()
            else:
                raise Exception("Missing required fields")
        return super().save(*args,**kwargs)



# Model to keep track of repayments
class LoanRepayment(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='loan_repayments'
    )
    user = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='loan_repayments'
    )
    loan = models.ForeignKey(
        LoanApplication,
        on_delete=models.CASCADE,
        related_name='loan_repayments'
    )
    date_paid = models.DateField(
        auto_now_add=True
    )
    amount_paid = models.DecimalField(
        decimal_places=2,
        max_digits=12
    )
    is_full_payment = models.BooleanField(
        default=False
    )
    payment_period = models.DateField(
        help_text='Month this payment is for. eg: 01-12-2025'
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def check_is_full_payment(self):
        monthly_installment = self.loan.monthly_installments

        # Total paid for the same loan/user/month
        total_paid = LoanRepayment.objects.filter(
            loan=self.loan,
            user=self.user,
            payment_period=self.payment_period
        ).aggregate(total=models.Sum('amount_paid'))['total'] or 0

        self.is_full_payment = total_paid >= monthly_installment

    def update_total_amount_paid(self):
        amount = self.amount_paid

        # Add amount to Loans total_amount_paid field
        self.loan.total_amount_paid += amount

        # save update
        self.loan.save()
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None  # Check if this is a new record

        if is_new:
            super().save(*args, **kwargs)  # Save to get an ID

        # Run dependent logic
        self.check_is_full_payment()

        # Update related loan object
        self.update_total_amount_paid()  #This auto updates the Loan object

        # Save
        super().save(update_fields=['is_full_payment'])



"""
ACCOUNT MAPPINGS FOR LOANS
"""
class LoanAccountMapping(models.Model):
    ACTIONS = [
        ('loan_application_approval','Loan application approval'),
        ('loan_disbursement','Loan disbursement'),
        ('loan_repayment','Loan repayment')
    ]
    name = models.CharField(
        max_length=100,
        choices=ACTIONS,
        default=''
    )
    debit_acc = models.ForeignKey(
        ChartOfAccounts,
        on_delete=models.PROTECT,
        related_name='loan_debit_mapping'
    )
    credit_acc = models.ForeignKey(
        ChartOfAccounts,
        on_delete=models.PROTECT,
        related_name='loan_credit_mapping'
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name='loan_mappings'
    )
    created_on = models.DateTimeField(auto_now_add=True,null=True)
    updated_on = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields = ['tenant','name'],
                name='unique_mapping_per_tenant'
            )
        ]

    def __str__(self):
        return f'Loan Mapping - {self.name} for {self.tenant.name}'
    
    def clean(self):
        if self.debit_acc == self.credit_acc:
            raise ValidationError('Debits and Credits account cannot be the same')
    
    def save(self,*args,**kwargs):
        self.clean()
        super().save(*args,**kwargs)