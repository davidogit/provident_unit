import random
import os
from django.db import IntegrityError, models,transaction
from django.dispatch import receiver
from django.db.models.signals import pre_save
from django.urls import reverse
from MultiScheme.models import InvestmentScheme,Tenant
from django.conf import settings
from django.core.exceptions import ValidationError
from .generate_invoice import generate_invoice_number,generate_short_alpha_numeric_id
from Chart_of_Accounts.models import BankAccount
from django.core.validators import FileExtensionValidator

class InvestmentDetail(models.Model):
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
        default=''
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
        max_length=255
    )
    account_number = models.CharField(
        max_length=255
    )
    principal_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )
    interest_percentage = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        null=False,
        blank=False
    )
    rollover_interest_percentage = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        default=0.00)
    interest_start_date = models.DateField(
        null=False,
        blank=False
    )
    interest_end_date = models.DateField(
        null=False,
        blank=False
    )
    created_date = models.DateField(
        auto_now_add=True
    )
    updated_date = models.DateTimeField(
        auto_now=True
    )
    roll_over = models.BooleanField(
        default=False
    )
    rollover_count = models.IntegerField(
        default=0
    )
    _remaining_days = models.PositiveIntegerField(
        default=0
    )
    _status = models.CharField(
        max_length=20,
        default='Pending'
    )
    approval_status = models.BooleanField(
        default=False
    )
    closing_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )
    termination_status = models.BooleanField(
        default=False
    )
    interest_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )
    years = models.DecimalField(
        max_digits=4,
        decimal_places=0,
        null=False
    ) #Time the money is invested or borrowed for, in years.
    compounding_frequency = models.PositiveIntegerField(
        null=False
    ) # Number of times the interest is compounded per year.
    type_of_tbill = models.CharField(
        max_length=10,
        default=''
    )#specifies if 91,182,365 day for only Tbill


    def calculate_inv_interest(self):
        # # Calculation involving compound interest
        p = self.principal_amount
        r = self.interest_percentage/100
        t = self.years
        n = self.compounding_frequency # daily,monthly,quaterly,yearly

        c = p*(1+(r/n))**(n*t) #compound interest
        interest = c-p #interest amount only

        return interest

    def calculate_tenure(self):
        return (self.interest_end_date - self.interest_start_date).days
    
    @property
    def tenure(self):
        return self.calculate_tenure()

    def calculate_rollover_principal(self):
        return (self.interest_amount + self.principal_amount)  # Simplified to directly return interest_amount
    
    # Remaining Days
    @property
    def remaining_days(self):
        return self._remaining_days
    
    # remainig_days setter to allow write to remaining_days
    @remaining_days.setter
    def remaining_days(self,value):
        self._remaining_days = value

    # Status of Investment to be set by task
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

    @property
    def rollover_principal(self):
        return self.calculate_rollover_principal()

    def calculate_rollover_accumulated_amount(self):
        rollover_interest_percentage = self.rollover_interest_percentage or 0.0
        rollover_principal = self.rollover_principal or 0.0
        if rollover_interest_percentage == 0.0 or rollover_principal is None:
            return 0.0
        return rollover_principal + (rollover_principal * (rollover_interest_percentage / 100.0))
    
    @property
    def rollover_accumulated_amount(self):
        return self.calculate_rollover_accumulated_amount()

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
    _status = models.CharField(
        max_length=20,
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
    
    @property
    def status(self):
        return self._status
    
    @status.setter
    def status(self,value):
        self._status = value

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
    approved = models.BooleanField(
        default=False
    )
    class Meta:
        ordering = ['-date_created']

    def update_total_amount(self):
        self.total_amount = sum(item.total_cost for item in self.items.all())
        self.save()

    def approve(self):
        self.approved = True
        PurchaseOrder.objects.create(
            requisition=self,
            amount=self.total_amount
        )
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
    quantity = models.IntegerField()
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=False
    )
    total_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
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
    )
    
    class Meta:
        ordering = ['-date_created']

    def __str__(self):
        return f'{self.requisition.tenant} | {self.id} | created at: {self.date_created}'
    
    def save(self, *args, **kwargs):
        if not self.id:
            self.id = generate_short_alpha_numeric_id(PurchaseOrder)
        return super().save(*args, **kwargs)


# Purchase Payment Invoice
class PaymentInvoice(models.Model):
    invoice_number = models.CharField(
        max_length=255
    )
    purchase_order = models.OneToOneField(
        PurchaseOrder,
        on_delete=models.DO_NOTHING,
        null=False,
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

    def save(self,*args,**kwargs):
        self.supplier = self.purchase_order.requisition.supplier
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
