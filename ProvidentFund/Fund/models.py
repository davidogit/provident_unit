import random
import string
from django.db import IntegrityError, models,transaction
from django.dispatch import receiver
from django.db.models.signals import pre_save
from django.urls import reverse
from MultiScheme.models import InvestmentScheme
from django.conf import settings
from django.core.exceptions import ValidationError
from .generate_invoice import generate_invoice_number

class InvestmentDetail(models.Model):
    invoice_number = models.CharField(max_length=8, unique=True,null=True,blank=True, editable=False)
    investment_scheme = models.ForeignKey(InvestmentScheme, on_delete=models.CASCADE, null=True, related_name='investments')
    T_bill = 'Treasury Bill'
    F_dep = 'Fixed Deposit'
    inv_type = [
        (T_bill,'Treasury Bill'),
        (F_dep, 'Fixed Deposit')
    ]
    investment_type = models.CharField(max_length=50, choices=inv_type, default='')
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
    account_type = models.CharField(max_length=50, choices=account, default=current)
    account_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=255)
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
    interest_start_date = models.DateField(null=False, blank=False)
    interest_end_date = models.DateField(null=False, blank=False)
    created_date = models.DateField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    roll_over = models.BooleanField(default=False)
    rollover_count = models.IntegerField(default=0)
    _remaining_days = models.PositiveIntegerField(default=0)
    _status = models.CharField(max_length=20, default='Pending')
    approval_status = models.BooleanField(default=False)
    closing_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
        )
    termination_status = models.BooleanField(default=False)
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
    compounding_frequency = models.PositiveIntegerField(null=False) # Number of times the interest is compounded per year.
    type_of_tbill = models.CharField(max_length=10, default='')#specifies if 91,182,365 day for only Tbill


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
    invoice_number = models.CharField(max_length=8, unique=True,null=True,blank=True, editable=False)
    investment_scheme = models.ForeignKey(InvestmentScheme, on_delete=models.CASCADE, null=True, related_name='delayed_interest')
    principal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )
    created_date = models.DateField(auto_now_add=True)
    remarks = models.CharField(max_length=50)
    _status = models.CharField(max_length=20, default='Not used')
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
    approved = models.BooleanField(default=False)
    date_paid = models.DateField(null=True)
    
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




class BankInterest(models.Model):
    investment_scheme = models.ForeignKey(InvestmentScheme, on_delete=models.CASCADE, null=True, related_name='bank_interest')
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
    bank_name = models.CharField(max_length=20, choices=names, default=GCB)
    branch = models.CharField(max_length=50)
    account_number = models.PositiveIntegerField()
    from_date = models.DateField()
    to_date = models.DateField()
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00
    )
    created_date = models.DateField(auto_now_add=True)
    remarks = models.CharField(max_length=50)
    _status = models.CharField(max_length=20, default='Not used')
    
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
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL, null=True,blank=True)
    action = models.CharField(max_length=10, choices=ACTIONS)
    model_name = models.CharField(max_length=255)
    timestamp = models.DateTimeField()
    object_id = models.CharField(max_length=255)
    changes = models.TextField() #description of changes made
    name = models.CharField(max_length=255, default='')

    def __str__(self):
        return f'{self.name} {self.action} at {self.timestamp}'



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
        return f"{self.bank_name} - {self.interest_rate}%"
