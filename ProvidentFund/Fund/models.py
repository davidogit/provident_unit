import random
import os
from django.db import IntegrityError, models,transaction
from django.dispatch import receiver
from django.db.models.signals import pre_save,pre_delete
from django.urls import reverse
from MultiScheme.models import InvestmentScheme,Tenant
from django.conf import settings
from django.core.exceptions import ValidationError
from ProvidentFund.settings import AUTH_USER_MODEL
from .generate_invoice import generate_invoice_number,generate_short_alpha_numeric_id
from Chart_of_Accounts.models import BankAccount, ChartOfAccounts, AccountingService
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class InvestmentDetail(models.Model):
    invoice_number = models.CharField(
        max_length=8,
        unique=True,
        null=True,
        blank=True,
        editable=False,
        help_text='specifies the item number'
    )
    investment_scheme = models.ForeignKey(
        InvestmentScheme,
        on_delete=models.CASCADE,
        null=True,
        related_name='investments'
    )
    T_bill = 'Treasury Bill'
    F_dep = 'Fixed Deposit'
    inv_type = [
        (T_bill,'Treasury Bill'),
        (F_dep, 'Fixed Deposit')
    ]
    investment_type = models.CharField(
        max_length=50,
        choices=inv_type,
        default='',
        help_text='specifies the type of investment'
    )
    current = 'Current'
    checking ='Checking'
    savings = 'Savings'
    fixed_deposit = 'Fixed Deposit'
    premium_checking = 'Premium Checking'
    business = 'Business'
    account = [
        (current,'Current'),
        (checking,'Checking'),
        (savings,'Savings'),
        (fixed_deposit,'Fixed Deposit'),
        (premium_checking,'Premium Checking'),
        (business,'Business')
    ]
    account_type = models.CharField(
        max_length=50,
        choices=account,
        default=current
    )
    account_name = models.CharField(
        max_length=255,
        null=False,
        blank=False
    )
    account_number = models.CharField(
        max_length=255,
        null=False,
        blank=False
    )
    principal_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        null=False,
        blank=False
    )
    interest_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        null=False,
        blank=False,
        help_text='specifies the interest rate'
    )
    interest_start_date = models.DateField(
        null=False,
        blank=False,
        help_text='specifies the date the investment is starts accruing interest'
    )
    interest_end_date = models.DateField(
        null=False,
        blank=False,
        help_text='specifies the maturity date of the investment'
    )
    created_date = models.DateField(
        auto_now_add=True
    )
    updated_date = models.DateTimeField(
        auto_now=True
    )
    roll_over = models.BooleanField(
        default=False,
        help_text='specifies if the investment has been rolled over'
    )
    rollover_count = models.IntegerField(
        default=0,
        help_text='specifies how many times the investment has been rolled over'
    )
    _remaining_days = models.PositiveIntegerField(
        default=0
    )
    _status = models.CharField(
        max_length=20,
        default='Pending'
    )
    approved = models.BooleanField(
        default=False,
        help_text='specifies if the investment is approved or not'
    )
    approval_status = models.BooleanField(
        default=False,
        help_text='specifies if matured investments have been recognized or not'
    )
    approved_by = models.ForeignKey(
        AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='approved_investments',
        null=True,
        blank=True
    )
    approved_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date investment was approved.'
    )
    rejected = models.BooleanField(
        default=False,
        help_text='If loan was rejected'
    )
    rejected_by = models.ForeignKey(
        AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='rejected_investments',
        null=True,
        blank=True
    )
    rejected_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date investment was rejected.'
    )
    realized_by = models.ForeignKey(
        AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='realized_investments',
        null=True,
        blank=True,
    )
    realized_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date investment was realized.'
    )
    closing_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        help_text='specifies the closing amount of the investment, value is entered during validating of matured investments'
    )
    termination_status = models.BooleanField(
        default=False,
        help_text='specifies if the investment is terminated or not'
    )
    interest_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )
    years = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=False,
        help_text='specifies how many years the money is invested or borrowed for'
    )
    compounding_frequency = models.PositiveIntegerField(
        null=False,
        help_text='specifies how often the interest is compounded'
    )
    type_of_tbill = models.CharField(
        max_length=10,
        default='',
        null=True,
        blank=True,
        help_text='specifies if 91,182,365 day for only T-bill'
    )


    def approve(self,**kwargs):
        """
        Approves an investment if it has not already been approved. This method handles
        the process of updating approval status and performing necessary accounting
        entries for the investment.

        Args:
            **kwargs: Arbitrary keyword arguments where:
                user: The user who is approving the investment.

        Raises:
            Exception: If the investment has already been approved.
        """
        if self.approved:
            raise Exception('Investment has already been approved')

        user = kwargs.get('user')
        scheme = self.investment_scheme
        tenant = scheme.tenant
        principal_amount = self.principal_amount

        with transaction.atomic():
            # Perform debit and credit
            accounting_service = AccountingService(tenant=tenant, user=user, scheme=scheme)
            action_name = 'Investment'
            description = 'Investment purchased'
            try:
                accounting_service.create_entry(action_name, principal_amount, description)
            except Exception as e:
                logger.error(f'Error creating accounting entry for {tenant.name} {action_name}: {e}')

            self.approved_by = user
            self.approved = True
            self.approved_date = timezone.now().date()
            self.save()


    def reject(self,**kwargs):
        """
        Rejects an investment if it has not already been approved or rejected. Updates
        the status of the investment to reject, records the user who performed the
        rejection, and sets the rejection date to the current date.

        Raises
        ------
        Exception
            If the investment has already been rejected.
        Exception
            If the investment has already been approved.

        Parameters
        ----------
        **kwargs : dict
            Additional keyword arguments. Expected to contain the following:
            'user' : Any
                The user who is rejecting the investment.
        """
        if self.rejected:
            raise Exception('Investment has already been rejected')
        if self.approved:
            raise Exception('Investment has already been approved')

        user = kwargs.get('user')

        with transaction.atomic():
            self.rejected_by = user
            self.rejected = True
            self.rejected_date = timezone.now().date()
            self.save()


    def realize_interest(self,**kwargs):
        if self.approval_status:
            raise Exception('Investment has already been realized')

        user = kwargs.get('user')
        closing_amount = kwargs.get('closing_amount')
        scheme = self.investment_scheme
        tenant = scheme.tenant

        with transaction.atomic():
            accounting_service = AccountingService(tenant=tenant, user=user, scheme=scheme)
            action_name = 'Realize Matured Investment'
            description = 'Realize Matured Investment'
            try:
                accounting_service.create_entry(action_name, self.interest_amount, description)

                # Compute and distribute members' actual profits earned from this investment
                from Fund.tasks import actual_member_interest
                actual_member_interest.delay(tenant.id, scheme.id, self.id)

                self.approval_status = True
                self.closing_amount = closing_amount
                self.realized_by = user
                self.realized_date = timezone.now().date()
                self.save()
                return True,'Investment has been realized successfully.'
            except ValidationError as val_e:
                logger.error(f'Error realizing investment: {val_e}')
                return False,str(val_e)
            except Exception as e:
                logger.error(f'Error realizing investment: {e}')
                return False,'An error occurred while realizing the investment'


    def calculate_inv_interest(self):
        # # Calculation involving compound interest
        p = self.principal_amount
        r = self.interest_percentage/100
        t = self.years
        n = self.compounding_frequency # daily,monthly,quarterly,yearly
        c = p*(1+(r/n))**(n*t) #compound interest
        interest = c-p #interest amount only
        return interest

    def calculate_tenure(self):
        return (self.interest_end_date - self.interest_start_date).days
    
    @property
    def tenure(self):
        return self.calculate_tenure()
    
    # Remaining Days
    @property
    def remaining_days(self):
        return self._remaining_days
    
    # remaining_days setter to allow writing to remaining_days
    @remaining_days.setter
    def remaining_days(self,value):
        self._remaining_days = value

    # Status of Investment to be set by a task
    @property
    def status(self):
        return self._status
    
    @status.setter
    def status(self, value):
        self._status = value
    
    # Set remaining days and status 
    def save(self, *args, **kwargs):
        # Set interest amount 
        self.interest_amount = self.calculate_inv_interest()

        if not self.pk:
            self._remaining_days = self.calculate_tenure()

        # Prevent updates to investments after the status has changed to active
        if self.pk and self.status in ['Active',]:
            raise ValidationError('This investment is closed and can no longer be edited')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.account_name}'s Investment"
    
    def get_absolute_url(self):
        return reverse('investment_detail', kwargs={'pk': self.pk},) 
    
@receiver(pre_save,sender=InvestmentDetail)
def set_invoice_number(sender,instance,**kwargs):
    if not instance.invoice_number:
        while True:
            obj = instance.investment_type
            obj_prefix = 'TB' if obj=='Treasury Bill' else 'FD'
            invoice_number = generate_invoice_number()
            new_invoice_number = f'{obj_prefix}{invoice_number}'
            

            if not InvestmentDetail.objects.filter(invoice_number=new_invoice_number).exists():
                instance.invoice_number = new_invoice_number
                break


class DelayedInterest(models.Model):
    invoice_number = models.CharField(
        max_length=8,
        unique=True,
        null=True,
        blank=True,
        editable=False
    )
    investment_scheme = models.ForeignKey(
        InvestmentScheme,
        on_delete=models.CASCADE,
        null=True,
        related_name='delayed_interest'
    )
    principal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )
    created_date = models.DateField(
        auto_now_add=True
    )
    remarks = models.CharField(
        max_length=50
    )
    choice = [
        ('Paid','Paid'),
        ('Not Paid','Not Paid')
    ]
    status = models.CharField(
        max_length=20,
        choices=choice,
        default='Not paid'
    )
    # due_date = models.DateField()
    rate_d_int = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00
    )
    interest = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )
    period_of_interest_calculation = models.PositiveIntegerField() #period over which interest is to be calculated.
    approved = models.BooleanField(
        default=False
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    date_paid = models.DateTimeField(
        auto_now=True,
        null=True
    )
    

# SIGNAL FOR DelayedInterest
# Setting invoice number before saving DI
@receiver(pre_save, sender=DelayedInterest)
def set_invoice_number(sender, instance, **kwargs):
    if not instance.invoice_number:
        while True:
            invoice_number = generate_invoice_number()
            new_invoice_number = f'DI{invoice_number}'
            try:
                with transaction.atomic():  # Ensures atomic operation
                    if not DelayedInterest.objects.filter(invoice_number=new_invoice_number).exists():
                        instance.invoice_number = new_invoice_number
                        break
            except IntegrityError:
                # If IntegrityError occurs (i.e., race condition), try again
                continue



# NOT IN USE ATM
class BankInterest(models.Model):
    investment_scheme = models.ForeignKey(
        InvestmentScheme,
        on_delete=models.CASCADE,
        null=True,
        related_name='bank_interest'
    )
    GCB ='GCB'
    ADB ='ADB'
    CBG = 'CBG'
    HFC = 'HFC'
    Ecobank = 'Ecobank'
    ABSA = 'ABSA'
    names = [
        (GCB,'GCB'),
        (ADB,'ADB'),
        (CBG,'CBG'),
        (HFC,'HFC'),
        (Ecobank,'Ecobank'),
        (ABSA,'ABSA'),
    ]
    bank_name = models.CharField(
        max_length=20,
        choices=names,
        default=GCB
    )
    branch = models.CharField(
        max_length=50
    )
    account_number = models.PositiveIntegerField()
    from_date = models.DateField()
    to_date = models.DateField()
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )
    created_date = models.DateField(
        auto_now_add=True
    )
    remarks = models.CharField(
        max_length=50
    )
    _status = models.CharField(
        max_length=20,
        default='Not used'
    )
    
    @property
    def status(self):
        return self._status
    
    @status.setter
    def status(self,value):
        self._status = value






# AUDIT TRAIL
class AuditTrail(models.Model):
    ACTIONS = [
        ('created','Created'),
        ('updated','Updated'),
        ('deleted','Deleted'),
        ('visited','Visit')
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    action = models.CharField(
        max_length=10,
        choices=ACTIONS
    )
    model_name = models.CharField(
        max_length=255
    )
    timestamp = models.DateTimeField()
    object_id = models.CharField(
        max_length=255
    )
    changes = models.TextField() #description of changes made
    name = models.CharField(
        max_length=255,
        default=''
    )

    def __str__(self):
        return f'{self.name} | {self.action} | visited at: {self.timestamp}'



class BankInterestRate(models.Model):
    bank_name = models.CharField(max_length=100)
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00
        )  
    effective_date = models.DateField()  # Date from when this interest rate is effective

    class Meta:
        ordering = ['-effective_date']  # Order by most recent rates
        
    def __str__(self):
        return f"{self.bank_name} | {self.interest_rate}%"



# Schedule dates for General Payment Model
class ScheduledPaymentDates(models.Model):
    month_choices = [
        ('1','January'),
        ('2','February'),
        ('3','March'),
        ('4','April'),
        ('5','May'),
        ('6','June'),
        ('7','July'),
        ('8','August'),
        ('9','September'),
        ('10','October'),
        ('11','November'),
        ('12','December'),
    ]
    # date_of_payment = models.DateField(null=False)
    day = models.PositiveIntegerField(
        null=False,
        blank=False
    )
    month = models.CharField(
        max_length=10,
        null=False,
        blank=False,
        default='',
        choices=month_choices
    )
    payout_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=False,
        blank=False
    )
    scheme = models.ForeignKey(
        InvestmentScheme,
        on_delete=models.CASCADE,
        null=False,
        related_name='scheduledPaymentDate'
    )
    bank = models.ForeignKey(
        BankAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=False,
        related_name='scheduledPaymentDate'
    )
    approved = models.BooleanField(
        default=False
    )

    def __str__(self):
        return f'{self.tenant} | {self.scheme} || {self.month} {self.day}'



# SUPPLIERS
class Suppliers(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=False,
        related_name='suppliers'
    )
    name = models.CharField(
        max_length=255,
        null=False
    )
    bank = models.CharField(
        max_length=255,
        null=True
    )
    account_number = models.CharField(
        max_length=20,
        null=True
    )
    email = models.EmailField(
        null=True
    )
    phone = models.CharField(
        max_length=12,
        null=True
    )
    address = models.CharField(
        max_length=255
    )
    branch = models.CharField(
        max_length=255,
        null=True
    )
    date_added = models.DateTimeField(
        auto_now_add=True,
        null=True
    )


    def __str__(self):
        return f'{self.name} | added on: {self.date_added}'


# Requisition Model (Header)
class Requisition(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=False,
        related_name='requisitions'
    )
    supplier = models.ForeignKey(
        Suppliers,
        on_delete=models.SET_NULL,
        null=True,
        related_name='requisitions'
    )
    description = models.TextField(
        max_length=255,
        null=True,
        blank=True
    )
    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )
    date_created = models.DateTimeField(
        auto_now_add=True
    )
    tax_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        default=Decimal(0)
    )
    ready_for_approval = models.BooleanField(
        default=False
    )
    approved = models.BooleanField(
        default=False
    )
    approved_by = models.ForeignKey(
        AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_requisitions'
    )
    approved_date = models.DateField(
        null=True,
        blank=True
    )
    rejected = models.BooleanField(
        default=False
    )
    rejected_by = models.ForeignKey(
        AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rejected_requisitions'
    )
    rejected_date = models.DateField(
        null=True,
        blank=True
    )

    class Meta:
        ordering = ['-date_created']

    def update_total_amount(self):
        self.total_amount = sum(item.total_cost for item in self.items.all())
        self.save()

    def approve(self, **kwargs):
        """
        Approve the requisition and create a corresponding purchase order if it has not been approved or
        rejected previously.

        Raises:
            Exception: If the requisition is already approved.
            Exception: If the requisition is already rejected.

        Parameters:
            kwargs (dict): A dictionary of keyword arguments. Expected key is:
                - user: The user who approves the requisition.

        """
        if self.approved:
            raise Exception('Requisition has already been approved')
        if self.rejected:
            raise Exception('Requisition has already been rejected')

        user = kwargs.get('user')

        with transaction.atomic():
            self.approved = True
            self.approved_by = user
            self.approved_date = timezone.now().date()
            self.save()

            PurchaseOrder.objects.create(
                requisition=self,
                # Purchase order amount is sum of amount + tax
                amount=self.total_amount + self.tax_amount
            )

    def reject(self, **kwargs):
        """
        Rejects the current requisition. This operation marks the requisition as rejected
        and records relevant information such as the user who performed the rejection
        and the date when the rejection occurred. The operation must ensure that the
        requisition is not already rejected or approved to maintain data consistency.

        Parameters
        ----------
        **kwargs : dict
            A dictionary of keyword arguments. Must include the `user` parameter, which
            specifies the user performing the rejection (of any appropriate type).

        Raises
        ------
        Exception
            If the requisition has already been rejected.
        Exception
            If the requisition has already been approved.
        """
        if self.rejected:
            raise Exception('Requisition has already been rejected')
        if self.approved:
            raise Exception('Requisition has already been approved')

        user = kwargs.get('user')

        with transaction.atomic():
            self.rejected = True
            self.rejected_by = user
            self.rejected_date = timezone.now().date()
            self.save()


    def __str__(self):
        return f'{self.pk} | {self.description[:20]} | amount: {self.total_amount} | created at: {self.date_created}'


# Requisition Items Model
class RequisitionItem(models.Model):
    requisition = models.ForeignKey(
        Requisition,
        on_delete=models.CASCADE,
        related_name='items',
        null=False
    )
    item_name = models.CharField(
        max_length=255,
        null=False
    )
    quantity = models.IntegerField(
        default=0,
        null=True,
        blank=True
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=False
    )
    total_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        default=Decimal(0.0)
    )
    date_added = models.DateTimeField(
        auto_now_add=True,
        null=True
    )

    class Meta:
        ordering = ['-date_added']

    def save(self, *args, **kwargs):
        self.total_cost = self.quantity * self.amount
        super().save(*args, **kwargs)
        # Update the total_amount of the related requisition
        self.requisition.update_total_amount()

    def delete(self, *args, **kwargs):
        # Update the total_amount before deletion
        requisition = self.requisition
        super().delete(*args, **kwargs)
        requisition.update_total_amount()

    def __str__(self):
        return f'{self.item_name} | {self.requisition.description[:20]} | created at: {self.date_added}'
    


# Purchase Order Model
class PurchaseOrder(models.Model):
    id = models.CharField(
        max_length=12,
        primary_key=True,
        unique=True,
        editable=False
    )
    requisition = models.ForeignKey(
        Requisition,
        on_delete=models.DO_NOTHING,
        null=False,
        related_name='purchase_orders'
    )
    date_created = models.DateTimeField(
        auto_now_add=True,
        null=False
    )
    received = models.BooleanField(
        default=False
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        null=True,
        blank=True
    )#Tax inclusive
    # tax_amount = models.DecimalField(
    #     max_digits=15,
    #     decimal_places=2,
    #     null=True,
    #     blank=True
    # )
    
    class Meta:
        ordering = ['-date_created']

    def __str__(self):
        return f'{self.requisition.tenant} | {self.id} | created at: {self.date_created}'
    
    def save(self, *args, **kwargs):
        # self.tax_amount = self.requisition.tax_amount
        if not self.id:
            self.id = generate_short_alpha_numeric_id(PurchaseOrder)
        return super().save(*args, **kwargs)


# Purchase Payment Invoice
class PaymentInvoice(models.Model):
    invoice_number = models.CharField(
        max_length=255,
        unique=True,
        primary_key=True
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.DO_NOTHING,
        null=False,
        related_name='payment_invoice'
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=False
    )
    supplier = models.ForeignKey(
        Suppliers,
        on_delete=models.DO_NOTHING,
        null=False
    )
    created_date = models.DateTimeField(
        auto_now_add=True,
        null=True
    )
    approved = models.BooleanField(
        default=False
    )
    paid = models.BooleanField(
        default=False
    )
    date_paid = models.DateTimeField(
        null=True,
        blank=True
    )
    withholding_tax = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    debit_account = models.ForeignKey(
        ChartOfAccounts,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_invoice'
    )#Specifies account to debit when creating an invoice for a PO

    def save(self,*args,**kwargs):
        self.supplier = self.purchase_order.requisition.supplier
        return super().save(*args,**kwargs)




"""""
Received model to keep track of total number of items received in a Purchase order
"""""
class ReceivedItems(models.Model):
    purchase_order = models.OneToOneField(
        PurchaseOrder,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name='received_items'
    )
    total_number_of_items = models.PositiveBigIntegerField(
        null=True,
        blank=True
    )
    number_of_items_received = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        default=0
    )
    number_of_items_remaining = models.PositiveBigIntegerField(
        null=True,
        blank=True
    )
    total_purchase_order_amount=models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    amount_to_pay = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        default=Decimal(0.0)
    )

    def save(self,*args,**kwargs):
        if self.purchase_order:
            if not self.total_number_of_items:
                items = self.purchase_order.requisition.items.all()
                # Total number of items
                self.total_number_of_items=sum(item.quantity for item in items)

            # Total amount
            if not self.total_purchase_order_amount:
                self.total_purchase_order_amount = self.purchase_order.amount

                # Set balance to same as total amount on first save
                self.balance = self.purchase_order.amount

            # Remaining quantity to be received
            self.number_of_items_remaining = self.total_number_of_items-self.number_of_items_received

            # Update status of purchase order
            if self.number_of_items_remaining == 0:
                self.purchase_order.received = True
                self.purchase_order.save()

        return super().save(*args,**kwargs)


# MODEL FOR EXCEL FILES SENT TO BANK
class BankSheet(models.Model):
    name = models.CharField(
        max_length=255,
        null=False,
        blank=False
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name='bank_sheet'
    )
    scheme = models.ForeignKey(
        InvestmentScheme,
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
        related_name='bank_sheet'
    )
    def upload_file(self,filename):
        tenant_name=self.tenant.name
        return os.path.join('File_uploads',tenant_name,'SCHEDULED_PAYOUTS',filename)
    
    excel_file = models.FileField(
        null=True,
        blank=True,
        upload_to=upload_file,
        validators=[FileExtensionValidator(allowed_extensions=['xls','xlsx'])]
    )

    def __str__(self):
        return f'{self.tenant.name} - Scheduled Payout File - {self.id}'
