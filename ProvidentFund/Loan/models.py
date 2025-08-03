from django.db import IntegrityError, models
from Member.models import Member
from django.conf import settings
from MultiScheme.models import Tenant
from decimal import Decimal,ROUND_HALF_UP
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import UniqueConstraint, Sum
from django.db import transaction
import datetime

from ProvidentFund.settings import AUTH_USER_MODEL

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
        choices=[('FLAT','Flat'),('REDUCING','Reducing')], default='FLAT',
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
        help_text='Requested amount(Principal of loan) to be paid to member.'
    )
    interest_amount = models.DecimalField(
        decimal_places=2,
        max_digits=12,
        default=Decimal(0),
        help_text='Interest amount to be paid on this loan.'
    )
    purpose = models.TextField()
    status = models.CharField(
        choices=STATUS_CHOICES,
        default='PENDING',
        max_length=10
    )
    is_loan_fully_paid = models.BooleanField(
        default=False,
        help_text='Indicates if the loan has been fully paid'
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
    disbursed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='disbursed_loans',
        null=True,
        blank=True
    )
    disbursement_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date loan was paid to Member.'
    )
    rejected = models.BooleanField(
        default=False,
        help_text='If loan was rejected'
    )
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='rejected_loans',
        null=True,
        blank=True
    )
    rejected_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date loan was rejected.'
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
    remaining_principal = models.DecimalField(
        decimal_places=2,
        max_digits=12,
        blank=True,
        null=True,
        default=Decimal(0),
        help_text="Remaining Principal of loan automatically updated when payment is recorded"
    )
    accrued_interest_to_date = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal(0),
        help_text="Shows accrued interest to date, and automatically calculated and updated"
    )
    last_interest_accrual_date = models.DateField(
        null=True,
        blank=True,
        help_text="Keeps track of last date interest was accrued to prevent multiple calculation for a single day."
    )
    note = models.TextField(
        null=True,
        blank=True,
        help_text='Optional note or reason for when the loan is rejected or approved'
    )

    def __str__(self):
        return f'Loan application: id: {self.id} - {self.user.user.username} - Amount- {self.amount_requested}.'


    @property
    def outstanding_balance(self):
        return self.remaining_principal + self.accrued_interest_to_date

    @property
    def total_principal_paid(self):
        """
        Returns the total principal paid from all loan repayments.

        Calculates the sum of the 'principal_paid' field across all related
        loan repayment records and returns the total. If no repayments are
        found or no principal amount is paid, it defaults to Decimal('0.00').

        Returns:
            Decimal: The total amount of principal paid aggregated from
            loan repayments.
        """
        return self.loan_repayments.aggregate(
            total=Sum('principal_paid')
        )['total'] or Decimal('0.00')
    

    """
    PROCESSING FEE ON LOAN
    """
    def loan_processing_fee_flat(self):
        """
        Calculates and returns the loan processing fee based on a flat percentage.

        Computes the processing fee using the loan type's fee percentage and the
        requested loan amount, rounding the result to two decimal places.

        Returns:
            Decimal: The calculated processing fee for the loan.
        """
        fee_percentage_in_decimal = self.loan_type.loan_fee_percentage/Decimal('100')
        processing_fee = Decimal(self.amount_requested*fee_percentage_in_decimal)

        return processing_fee.quantize(Decimal("0.01"),rounding= ROUND_HALF_UP)
    

    """
    DISBURSEMENT AMOUNT
    """
    def disbursement_amount(self):
        """
        Calculates the disbursement amount by subtracting the loan processing fee
        from the requested loan amount. The result is rounded to two decimal places
        using the HALF_UP rounding method.

        Returns:
            Decimal: The disbursement amount rounded to two decimal places.
        """
        return Decimal(self.amount_requested - self.loan_processing_fee_flat()).quantize(Decimal("0.01"),rounding= ROUND_HALF_UP)


    """
    CALCULATE MONTHLY FLAT INSTALLMENTS USING EMI(
            REDUCING BALANCE OR FLAT
        )
    """
    def calculate_monthly_installments(self, principal_override=None):
        """
        Calculates the monthly installment amount (EMI) based on the loan parameters.

        The method computes the EMI for both "FLAT" and "REDUCING" interest calculation
        types. It considers the requested loan amount, annual interest rate, tenure in
        months, and interest calculation type. If the interest rate is zero, a simple
        division of the amount over the tenure is done. For "FLAT" type, the EMI is
        calculated by dividing the total payable amount (principal + total interest)
        over the tenure. For the "REDUCING" type, the standard reducing balance formula
        is used. An exception is raised for invalid interest calculation types.

        Returns the EMI as a Decimal rounded to two decimal places.

        Raises:
            ValueError: If the interest calculation type is invalid.

        Returns:
            Decimal: The monthly EMI value.
        """
        p = principal_override if principal_override is not None else self.amount_requested
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

                #update interest field on loan application
                self.interest_amount = total_interest.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            elif self.loan_type.interest_calculation_type == 'REDUCING':
                # Reducing balance formula (standard EMI)
                numerator = p * r * (1 + r) ** T
                denominator = ((1 + r) ** T) - 1
                emi = numerator / denominator

                #update interest field on loan application
                self.interest_amount = ((emi * T) - p).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)  # Total interest paid over the tenure
            else:
                raise ValueError("Invalid interest calculation type.")

        return emi.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        
    """
    APPROVE LOAN AND GENERATE SCHEDULE-- BY ADMIN
    """ 
    def approve(self, **kwargs):
        """
        Approves the loan request, updates its status, sets approval details, and
        generates the amortization schedule.

        Parameters:
        user : Any
            The user who approves the loan.

        Raises:
        Exception
            If the loan is already approved and processed.
        """
        if self.approved:
            raise Exception("Loan already processed.")

        user = kwargs.get('user')

        with transaction.atomic:
            # Generate amortization schedule
            build_amortization_schedule(loan=self, principal=self.amount_requested)

            # initialize remaining_principal upon loan approval
            self.remaining_principal = self.amount_requested

            # update loan details
            self.status = 'APPROVED'
            self.approved_by = user
            self.approved = True
            self.approval_date = timezone.now().date()
            self.save()


    """
    DISBURSE LOAN -- BY ADMIN
    """
    def disburse_loan(self, user):
        """
        Disburses the loan if it has been approved and not already disbursed.

        This method checks the current status of the loan to ensure it has been
        approved but not yet disbursed. If the loan is in a valid state, it proceeds
        to mark the loan as disbursed, record the user who performed the disbursement,
        and set the disbursement date to the current time.

        Raises:
            Exception: If the loan has not been approved.
            Exception: If the loan has already been disbursed.
        """
        if not self.approved:
            raise Exception("Loan not approved yet.")
        if self.disbursed:
            raise Exception("Loan already disbursed.")

        self.status = 'DISBURSED'
        self.disbursed_by = user
        self.disbursed = True
        self.disbursement_date = timezone.now()
        self.save()


    def reject(self,**kwargs):
        """
        Rejects the loan application, updates its status, and records the rejection details.

        This method sets the loan's status to 'REJECTED', marks it as rejected, and
        records the user who rejected it along with an optional note explaining the
        reason for rejection.

        Parameters:
            user: The user who is rejecting the loan.
            note: An optional note explaining the reason for rejection.

        Raises:
            Exception: If the loan has already been approved or processed.
        """
        if self.approved or self.disbursed:
            raise Exception("Loan already processed.")

        user = kwargs.get('user')
        note = kwargs.get('comment', None)

        self.status = 'REJECTED'
        self.rejected = True
        self.rejected_by = user
        self.note = note
        self.rejected_date = timezone.now()
        self.save()


    """
    HANDLE FULLY REPAYMENT OF LOAN
    """
    def handle_full_repayment(self):
        """
        Handles the process of marking a loan as fully repaid. This entails updating the
        loan's status, flagging it as fully paid, and marking all unpaid installments
        in the loan's amortization schedule as paid in an atomic transaction.

        Raises:
            Exception: If the loan is already marked as fully paid.
        """
        if self.is_loan_fully_paid:
            raise Exception("Loan already marked as fully paid.")

        with transaction.atomic():
            # Update loan status
            self.status = 'REPAID'
            self.is_loan_fully_paid = True
            self.save()

            # Update the amortization schedule to mark all installments as paid
            amortizations = self.amortization_schedule.filter(is_paid=False)
            if amortizations:
                for amortization in amortizations:
                    amortization.is_paid = True
                    amortization.payment_status = 'PAID'

                self.amortization_schedule.model.objects.bulk_update(
                    amortizations,
                    ['is_paid', 'payment_status']
                )

    """
    METHOD TO APPLY TOP-UP
    """
    def apply_topup(self, topup: 'LoanTopUp'):
        """
        Applies a top-up to an existing loan. This method updates the loan's amount
        requested, tenure, and related amortization schedule based on the provided
        top-up details. Deleted unpaid amortization schedule entries are replaced with
        newly calculated ones based on the updated loan parameters.

        Attributes
        ----------
        self.amount_requested : Decimal
            The total amount requested for the loan, including the new top-up amount.
        self.tenure_months : int
            The updated tenure of the loan in months, adjusted if a new tenure is
            provided in the top-up.
        self.loan_repayments : QuerySet
            QuerySet representing loan repayments, used to calculate the total
            principal paid.
        self.amortization_schedule : QuerySet
            QuerySet representing the loan's amortization schedule entries.
        self.loan_type : ForeignKey (LoanType)
            The associated loan type, which determines the interest rate and interest
            calculation type.
        self.tenant : Any
            The tenant related to the loan.
        self.user : Any
            The user associated with the loan.

        Parameters
        ----------
        topup : LoanTopUp
            Object containing loan top-up details, including the top-up amount and
            new tenure months.
        """
        with transaction.atomic():
            # Update loan values
            self.amount_requested += topup.topup_amount
            if topup.new_tenure_months > 0:
                self.tenure_months = topup.new_tenure_months
            self.save()

            # Delete only unpaid schedule entries
            self.amortization_schedule.filter(is_paid=False).delete()

            # Paid installments count
            paid_count = self.amortization_schedule.filter(is_paid=True).count()
            start_installment_number = paid_count + 1

            # Calculate remaining balance
            total_principal_paid = self.loan_repayments.aggregate(total=Sum('principal_paid'))['total'] or Decimal('0.00')
            new_principal = self.amount_requested - total_principal_paid

            # Start from today
            start_date = timezone.now().date()
            annual_rate = self.loan_type.loan_interest_rate
            r = Decimal(annual_rate) / Decimal('1200')
            T = Decimal(self.tenure_months)

            monthly_installment = self.calculate_monthly_installments(principal_override=new_principal)
            # Update monthly installments
            self.monthly_installments = monthly_installment
            self.save()

            remaining_balance = new_principal

            schedule_list = []

            for i in range(start_installment_number, int(T) + 1):
                if self.loan_type.interest_calculation_type == 'FLAT':
                    interest_component = (new_principal * Decimal(annual_rate) / Decimal('12')) / Decimal('100')
                    principal_component = monthly_installment - interest_component
                else:  # REDUCING
                    interest_component = (remaining_balance * r).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    principal_component = monthly_installment - interest_component

                if principal_component > remaining_balance:
                    principal_component = remaining_balance

                schedule_entry = LoanAmortizationSchedule(
                    tenant=self.tenant,
                    user=self.user,
                    loan=self,
                    installment_number=i,
                    installment_date=start_date,
                    principal_component=principal_component,
                    interest_component=interest_component,
                    total_installment_amount=principal_component + interest_component,
                    remaining_balance=(remaining_balance - principal_component).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
                )

                schedule_list.append(schedule_entry)
                remaining_balance -= principal_component
                start_date += datetime.timedelta(days=30)

            LoanAmortizationSchedule.objects.bulk_create(schedule_list)
    

    def apply_repayment(self, principal_component: 'Decimal', interest_component: 'Decimal'):

        self.accrued_interest_to_date -= interest_component
        self.remaining_principal -= principal_component
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
        # self.calculate_monthly_installments()
        return super().save(*args,**kwargs)



"""
LOAN AMORTIZATION SCHEDULE MODEL
"""
class LoanAmortizationSchedule(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='loan_amortization_schedules'
    )
    user = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='loan_amortization_schedules'
    )
    loan = models.ForeignKey(
        LoanApplication,
        on_delete=models.CASCADE,
        related_name='amortization_schedule'
    )
    installment_number = models.PositiveIntegerField(
        help_text='Installment number (1, 2, 3, ...)'
    )
    installment_date = models.DateField(
        help_text='Expected payment date for this installment'
    )
    principal_component = models.DecimalField(
        decimal_places=2,
        max_digits=12
    )
    interest_component = models.DecimalField(
        decimal_places=2,
        max_digits=12
    )
    total_installment_amount = models.DecimalField(
        decimal_places=2,
        max_digits=12
    )
    remaining_balance = models.DecimalField(
        decimal_places=2,
        max_digits=12
    )
    is_paid = models.BooleanField(
        default=False,
        help_text='Indicates if this installment has been paid'
    )
    payment_status = models.CharField(
        max_length=10,
        choices=[
            ('PENDING', 'Pending'),
            ('PAID', 'Paid'),
            ('OVERDUE', 'Overdue')
        ],
        default='PENDING',
        help_text='Current status of this installment payment'
    )
    created_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return f'Loan: {self.loan.id} - Installment {self.installment_number}'




# TODO Figure out how to handle repayments and also track them with amortization schedule
# Model to keep track of repayments
class LoanRepayment(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='loan_repayments'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='loan_repayments',
        null=True,
        help_text='Assigned when a repayment is made by an admin or staff member'
    )
    loan = models.ForeignKey(
        LoanApplication,
        on_delete=models.CASCADE,
        related_name='loan_repayments'
    )
    date_paid = models.DateField(
        auto_now_add=True
    )
    principal_paid = models.DecimalField(
        decimal_places=2,
        max_digits=12,
        default=Decimal(0),
        help_text='Principal amount paid for this repayment'
    )
    interest_paid = models.DecimalField(
        decimal_places=2,
        max_digits=12,
        default=Decimal(0),
        help_text='Interest amount paid for this repayment'
    )
    is_full_payment = models.BooleanField(
        default=False,
        help_text='Indicates if this repayment covers the full monthly installment'
    )
    payment_period = models.DateField(
        help_text='Month this payment is for. eg: 01-12-2025',
        null=True
    )
    payment_type = models.CharField(
        max_length=20,
        choices= [
            ('FULL', 'full'),
            ('INSTALLMENT', 'installment'),
            ('PARTIAL', 'partial'),
            ('NONE', 'none')
        ],
        default='NONE',
        help_text='Indicates if this repayment covers the full monthly installment'
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    # def check_is_full_payment(self):
    #     """
    #     Checks if the loan repayment for the current month equals or exceeds the
    #     monthly installment amount. This indicates whether the payment is fully
    #     settled.
    #
    #     Attributes:
    #         is_full_payment (bool): A flag indicating if the total payment made
    #                                 for the current loan and payment period meets or
    #                                 exceeds the required monthly installment amount.
    #
    #     Raises:
    #         DoesNotExist: If the `LoanRepayment` object lookup fails for the specified
    #                       loan and payment period.
    #     """
    #     monthly_installment = self.loan.monthly_installments
    #
    #     # TODO ensure to refactor the filtering for LoanRepayment
    #     # Total paid for the same loan/user/month
    #     total_paid = LoanRepayment.objects.filter(
    #         loan=self.loan,
    #         payment_period=self.payment_period
    #     ).aggregate(total=models.Sum('amount_paid'))['total'] or 0
    #
    #     self.is_full_payment = total_paid >= monthly_installment

    def update_total_amount_paid(self):
        """
        Updates the total amount paid toward a loan.

        This method adds the current payment amount to the total amount paid
        on the associated loan and saves the updated loan data.

        Raises:
            None
        """
        amount = self.principal_paid + self.interest_paid

        # Add amount to the Loans total_amount_paid field
        self.loan.total_amount_paid += amount

        # save update
        self.loan.save()
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None  # Check if this is a new record

        if is_new:
            # update the remaining_principal field on Loan object
            self.loan.apply_repayment(self.principal_paid,self.interest_paid)

            super().save(*args, **kwargs)  # Save to get an ID

        # Run dependent logic
        # self.check_is_full_payment()

        # Update the related loan object
        self.update_total_amount_paid()  #This auto updates the Loan object

        # Save
        super().save(update_fields=['is_full_payment'])



"""
LOAN TOP UP MODEL
"""
class LoanTopUp(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'PENDING'),
        ('APPROVED', 'APPROVED'),
        ('DISBURSED', 'DISBURSED'),
        ('REJECTED', 'REJECTED')
    ]
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='loan_topups'
    )
    user = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='loan_topups'
    )
    loan = models.ForeignKey(
        LoanApplication,
        on_delete=models.CASCADE,
        related_name='topups'
    )
    topup_amount = models.DecimalField(
        decimal_places=2,
        max_digits=12,
        help_text='Amount to be added to the existing loan'
    )
    topup_purpose = models.TextField(
        null=True,
        blank=True,
        help_text='Purpose of the top-up request, to be displayed to the member'
    )
    topup_reason = models.TextField(
        null=True,
        blank=True,
        help_text='Reason for the top-up request, to be displayed to the member'
    )
    disbursed_amount = models.DecimalField(
        decimal_places=2,
        max_digits=12,
        default=Decimal(0),
        help_text='Amount that has been disbursed to the member'
    )
    new_tenure_months = models.PositiveIntegerField(
        default=0,
        help_text='New tenure in months after the top-up is applied'
    )
    requested_at = models.DateTimeField(
        auto_now_add=True
    )
    disbursed = models.BooleanField(
        default=False,
        help_text='Indicates if the top-up has been disbursed'
    )
    approved = models.BooleanField(
        default=False,
        help_text='Indicates if the top-up has been approved'
    )
    rejected = models.BooleanField(
        default=False,
        help_text='Indicates if the top-up has been rejected'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='approved_topups',
        null=True,
        blank=True,
        help_text='User who approved the top-up'
    )
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='rejected_topups',
        null=True,
        blank=True,
        help_text='User who rejected the top-up'
    )
    disbursed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='disbursed_topups',
        null=True,
        blank=True,
        help_text='User who disbursed the top-up'
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Date when the top-up was approved'
    )
    rejected_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Date when the top-up was rejected'
    )
    disbursed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Date when the top-up was disbursed'
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='PENDING',
        help_text='Current status of the top-up request'
    )
    note = models.TextField(
        null=True,
        blank=True,
        help_text='Optional note or reason for when the top-up is rejected or approved'
    )


    def __str__(self):
        return f'Top Up of {self.topup_amount} for {self.loan.id}'

    def approve(self, **kwargs):
        """
        Approves the loan top-up request, updates its status, sets approval details,
        and marks it as approved.

        Parameters:
        user : Any
            The user who approves the top-up.

        Raises:
        Exception
            If the top-up is already approved or processed.
        """
        if self.approved or self.disbursed:
            raise Exception("Top-up already processed.")

        user = kwargs.get('user')

        self.status = 'APPROVED'
        self.approved_by = user
        self.approved = True
        self.approved_at = timezone.now()
        self.save()

    def reject(self,**kwargs):
        """
        Rejects the loan top-up request, updates its status, sets rejection details,
        and marks it as rejected.

        Parameters:
        user : Any
            The user who rejects the top-up.
        note : str, optional
            An optional note explaining the reason for rejection.

        Raises:
        Exception
            If the top-up is already approved or processed.
        """
        if self.rejected:
            raise Exception("Top-up already rejected.")
        if self.approved or self.disbursed:
            raise Exception("Top-up already processed.")

        user = kwargs.get('user')
        note = kwargs.get('comment', None)

        self.status = 'REJECTED'
        self.rejected = True
        self.rejected_by = user
        self.rejected_at = timezone.now()
        self.note = note
        self.save()

    def disburse_topup(self, user):
        """
        Disburses a top-up loan only if it has been approved and not disbursed yet. Updates
        the status and related properties of the top-up, marks it as disbursed, and applies
        the top-up to the associated loan.

        Args:
            user: The user who is disbursing the top-up.

        Raises:
            Exception: If the top-up has not been approved.
            Exception: If the top-up has already been disbursed.
        """
        if not self.approved:
            raise Exception("Top-up not approved yet.")
        if self.rejected:
            raise Exception("Top-up has been rejected")
        if self.disbursed:
            raise Exception("Top-up already disbursed.")

        with transaction.atomic():
            self.status = 'DISBURSED'
            self.disbursed_by = user
            self.disbursed_at = timezone.now()
            self.disbursed = True
            self.disbursed_amount = self.disbursement_amount()  # Calculate disbursement amount
            self.disbursement_date = timezone.now()
            self.save()

    #       apply the top-up to the loan
            self.loan.apply_topup(self)

    def loan_processing_fee_flat(self):
        """
        Calculates and returns the loan processing fee based on a flat percentage.

        Computes the processing fee using the loan type's fee percentage and the
        requested loan amount, rounding the result to two decimal places.

        Returns:
            Decimal: The calculated processing fee for the loan.
        """
        fee_percentage_in_decimal = self.loan.loan_type.loan_fee_percentage / Decimal('100')
        processing_fee = Decimal(self.topup_amount * fee_percentage_in_decimal)

        return processing_fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def disbursement_amount(self):
        """
        Calculates the disbursement amount by subtracting the loan processing fee
        from the requested loan amount. The result is rounded to two decimal places
        using the HALF_UP rounding method.

        Returns:
            Decimal: The disbursement amount rounded to two decimal places.
        """
        return Decimal(self.topup_amount - self.loan_processing_fee_flat()).quantize(Decimal("0.01"),
                                                                                         rounding=ROUND_HALF_UP)


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



"""
METHOD TO HANDLE AMORTIZATION SCHEDULE GENERATION
"""
# def generate_amortization_schedule(self):
#     """
#     Generates an amortization schedule for this loan.
#     Deletes existing schedule first. Uses bulk_create for efficiency.
#     """
#     with transaction.atomic():
#         # Delete the existing schedule first
#         self.amortization_schedule.all().delete()
#
#         schedule_list = []
#
#         # Initial loan details
#         p = self.amount_requested
#         annual_rate = self.loan_type.loan_interest_rate
#         r = Decimal(annual_rate) / Decimal('1200')  # Monthly interest rate
#         T = Decimal(self.tenure_months)
#
#         monthly_installment = self.calculate_monthly_installments()
#         remaining_balance = p
#
#         # Start from disbursement_date if set, else today
#         current_date = self.disbursement_date or timezone.now().date()
#
#         for i in range(1, int(T) + 1):
#             if self.loan_type.interest_calculation_type == 'FLAT':
#                 interest_component = (p * Decimal(annual_rate) * (Decimal('1') / Decimal('12'))) / Decimal('100')
#                 principal_component = monthly_installment - interest_component
#             else:  # REDUCING balance method
#                 interest_component = (remaining_balance * r).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
#                 principal_component = monthly_installment - interest_component
#
#             # Guard against rounding errors on the last installment
#             if principal_component > remaining_balance:
#                 principal_component = remaining_balance
#
#             # Build schedule row
#             schedule_entry = LoanAmortizationSchedule(
#                 tenant=self.tenant,
#                 user=self.user,
#                 loan=self,
#                 installment_number=i,
#                 installment_date=current_date,
#                 principal_component=principal_component,
#                 interest_component=interest_component,
#                 total_installment_amount=principal_component + interest_component,
#                 remaining_balance=(remaining_balance - principal_component).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
#             )
#             schedule_list.append(schedule_entry)
#
#             # Update for next loop
#             remaining_balance -= principal_component
#             # Advance by approx 1 month (30 days)
#             current_date += datetime.timedelta(days=30)
#
#         # Efficient bulk insert
#         LoanAmortizationSchedule.objects.bulk_create(schedule_list)


"""
BUILD AMORTIZATION SCHEDULE
"""
def build_amortization_schedule(*, loan, principal, start_date=None):
    """
    Generates amortization schedule for given loan and principal.
    Deletes only unpaid entries and regenerates from start_date onward.
    """
    with transaction.atomic():
        # Step 1: Delete only unpaid schedule entries
        unpaid_qs = loan.amortization_schedule.exclude(is_paid=True)
        unpaid_qs.delete()

        # Step 2: Fetch the number of installments already paid
        paid_count = loan.amortization_schedule.filter(is_paid=True).count()

        # Step 3: Determine installment number offset
        start_installment_number = paid_count + 1

        schedule_list = []

        annual_rate = loan.loan_type.loan_interest_rate
        r = Decimal(annual_rate) / Decimal('1200')  # Monthly interest rate
        T = Decimal(loan.tenure_months)

        monthly_installment = loan.calculate_monthly_installments(principal_override=principal)
        remaining_balance = principal

        # update the loan's monthly installments
        loan.monthly_installments = monthly_installment
        loan.save()

        # Step 4: Determine the actual start date
        current_date = start_date or timezone.now().date()

        # Step 5: Generate only the remaining schedule entries
        for i in range(start_installment_number, int(T) + 1):
            if loan.loan_type.interest_calculation_type == 'FLAT':
                interest_component = (principal * Decimal(annual_rate) * (Decimal('1') / Decimal('12'))) / Decimal('100')
                principal_component = monthly_installment - interest_component
            else:
                interest_component = (remaining_balance * r).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                principal_component = monthly_installment - interest_component

            if principal_component > remaining_balance:
                principal_component = remaining_balance

            schedule_entry = LoanAmortizationSchedule(
                tenant=loan.tenant,
                user=loan.user,
                loan=loan,
                installment_number=i,
                installment_date=current_date,
                principal_component=principal_component,
                interest_component=interest_component,
                total_installment_amount=principal_component + interest_component,
                remaining_balance=(remaining_balance - principal_component).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                payment_status="Pending",  # Mark new entries as Pending
            )
            schedule_list.append(schedule_entry)

            remaining_balance -= principal_component
            current_date += datetime.timedelta(days=30)

        LoanAmortizationSchedule.objects.bulk_create(schedule_list)