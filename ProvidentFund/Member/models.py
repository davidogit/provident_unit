from django.db import models
from django.contrib.auth.models import User
from requests import options
from MultiScheme.models import Tenant
from django.conf import settings
import uuid

from contributions.models import StaffAPI
from MultiScheme.models import InvestmentScheme
from django.utils import timezone
# from simple_history.models import HistoricalRecords

# Create your models here.

class Member(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE,null=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='member')
    staff_id = models.PositiveIntegerField(unique=True, null=True, blank=False)
    tel_number = models.PositiveIntegerField()

    address = models.CharField(max_length=50, blank=True,null=True)
    date_of_birth = models.DateField( auto_now=False, auto_now_add=False, null=True)
    nationality = models.CharField(max_length = 50,blank=True, null=True)
    image = models.ImageField(upload_to='profile_images/', blank=True, null=True,default='profile_images/default_profile_pic.png')
    marital_status = models.CharField(max_length =50,blank=True, null=True)
    select ='select'
    male='Male'
    female = 'Female'
    other ='Other'
    gender = [
        (select ,'select'),
        (male ,'Male'),
        (female, 'Female'),
        (other,'Other'),
    ]
    gender = models.CharField(choices=gender, default='', max_length=10)
    employment_date = models.DateField(auto_now=False,auto_now_add=False, null=True)
    department = models.CharField(max_length = 200,blank=True, null=True)
    job_title = models.CharField(max_length = 200,blank=True, null=True)

    registration_date = models.DateTimeField(null=True)
    scheme_approval = models.BooleanField(default=False)

    # History
    # history = HistoricalRecords()
    
    investment_scheme = models.ForeignKey(InvestmentScheme, on_delete=models.CASCADE, null=True, blank=True)


    


    def __str__(self):
        return f'{self.user.username}\'s account'


# Approval Model
class SchemeApproval(models.Model):
    
    tenant = models.ForeignKey(Tenant,on_delete=models.CASCADE)
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    staff = models.ForeignKey(StaffAPI, on_delete=models.CASCADE)
    scheme = models.ForeignKey(InvestmentScheme, on_delete=models.CASCADE)
    applied_date = models.DateTimeField(auto_now_add=True)
    approval_date = models.DateTimeField(null=True,blank=True)
    application_date = models.DateTimeField(null=True,blank=True)
    approved_by_hr = models.BooleanField(default=False)

    # History
    # history = HistoricalRecords()

    # method to approve scheme applications
    def approve(self):
        self.approved_by_hr = True
        self.approval_date = timezone.now()
        self.save()

        # Add member to scheme(but in this case we have to set it on the StaffApi model)
        self.staff.investment_scheme.add(self.scheme)

































class TransactionHistory(models.Model):
    transaction_id  =models.UUIDField(default = uuid.uuid4,unique = True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE,null = True)
    staff = models.ForeignKey(StaffAPI, on_delete=models.CASCADE,null=True)
    member = models.ForeignKey(Member,on_delete=models.CASCADE,related_name="transactions")
    scheme = models.ForeignKey(InvestmentScheme, on_delete= models.CASCADE,related_name ="transactions")
    transaction_date = models.DateTimeField(auto_now_add=True,null=True, blank=True)
    DEPOSIT = 'Deposit'
    WITHDRAWAL = 'Withdrawal'
    transaction_type_choices = [
        (DEPOSIT,'Deposit'),
        (WITHDRAWAL,'Withdrawal')
    ]
    transaction_type = models.CharField(max_length=20, choices=transaction_type_choices,default=DEPOSIT)
    MOBILE_MONEY = 'MobileMoney'
    BANK_TRANSFER = 'BankTransfer'
    payment_method = [
        (MOBILE_MONEY,'Mobile Money'),
        (BANK_TRANSFER,'Bank Transfer')
    ]
    payment_method = models.CharField(max_length=20, choices=payment_method, default=MOBILE_MONEY)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference = models.TextField(max_length=255, blank=True)
    def __str__(self):
       return f"{self.transaction_type} - {self.amount} on {self.transaction_date}"
    
    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = uuid.uuid4()
        super().save(*args, **kwargs)

