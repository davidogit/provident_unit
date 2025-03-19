from decimal import Decimal
import os
from django.db import models,transaction
from django.contrib.auth.models import User
from requests import options
from MultiScheme.models import Tenant
from django.conf import settings
import uuid
from Chart_of_Accounts.models import BankAccount
from contributions.models import StaffAPI
from MultiScheme.models import InvestmentScheme
from django.utils import timezone
from django.core.validators import FileExtensionValidator
import random
from django.db import IntegrityError
from django.db.models import JSONField
from Fund.generate_invoice import generate_short_alpha_numeric_id


# Create your models here.

class Member(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='member'
    )
    staff_id = models.PositiveIntegerField(
        unique=True,
        null=True,
        blank=False
    )
    tel_number = models.CharField(
        max_length=10
    )

    address = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )
    date_of_birth = models.DateField(
        auto_now=False,
        auto_now_add=False,
        null=True
    )
    nationality = models.CharField(
        max_length = 50,
        blank=True,
        null=True
    )
    marital_status = models.CharField(
        max_length =50,
        blank=True,
        null=True
    )
    select ='select'
    male='Male'
    female = 'Female'
    other ='Other'
    gender_choice = [
        (select ,'select'),
        (male ,'Male'),
        (female, 'Female'),
        (other,'Other'),
    ]
    gender = models.CharField(
        choices=gender_choice,
        default='',
        max_length=10
    )
    employment_date = models.DateField(
        auto_now=False,
        auto_now_add=False,
        null=True
    )
    department = models.CharField(
        max_length = 200,
        blank=True,
        null=True
    )
    job_title = models.CharField(
        max_length = 200,
        blank=True,
        null=True
    )
    registration_date = models.DateTimeField(
        null=True
    )
    scheme_approval = models.BooleanField(
        default=False
    )
    investment_scheme = models.ForeignKey(
        InvestmentScheme,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='member'
    )


    def __str__(self):
        return f'{self.user.username}\'s account'
    

    # dynamic file path for document uploads
    def upload_image(self,filename):
        tenant_name = self.tenant.name
        user_name = self.user.username

        return os.path.join('File_uploads',tenant_name,user_name,filename)

    image = models.ImageField(
        upload_to=upload_image,
        blank=True,
        null=True,
        default='profile_images/default_profile_pic.png'
    )





# SCHEME APPLICATION MODEL
class SchemeApproval(models.Model):
    
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE
    )
    staff = models.ForeignKey(
        StaffAPI,
        on_delete=models.CASCADE
    )
    scheme = models.ForeignKey(
        InvestmentScheme,
        on_delete=models.CASCADE
    )
    # applied_date = models.DateTimeField(auto_now_add=True)
    approval_date = models.DateTimeField(
        null=True,
        blank=True
    )
    application_date = models.DateTimeField(
        null=True,
        blank=True
    )
    approved_by_hr = models.BooleanField(
        default=False
    )


    # dynamic file path for document uploads
    def upload_file(self,filename):
        tenant_name = self.tenant.name
        user_name = self.member.user.username

        return os.path.join('File_uploads',tenant_name,'MEMBER_UPLOADS',user_name,filename)


    document = models.FileField(
        blank=True,
        null=True,
        upload_to=upload_file,
        validators=[FileExtensionValidator(allowed_extensions=['pdf','docx'])]
    )


    # method to approve scheme applications
    def approve(self):
        self.approved_by_hr = True
        self.approval_date = timezone.now()
        self.save()

        # Add member to scheme(but in this case we have to set it on the StaffApi model)
        self.staff.investment_scheme.add(self.scheme)

class ExitApproval(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE
    )
    staff = models.ForeignKey(
        StaffAPI,
        on_delete=models.CASCADE
    )
    scheme = models.ForeignKey(
        InvestmentScheme,
        on_delete=models.CASCADE
    )
    reason = models.CharField(
        max_length=500,
        default=''
    )
    application_date = models.DateTimeField(
        auto_now_add=True,
        null=False,
        blank=True
    )
    approval_date = models.DateTimeField(
        null=True,
        blank=True
    )
    approved = models.BooleanField(
        default=False
    )

    def __str__(self):
        return f'{self.tenant.name} - {self.member.user.username}\'s EXIT application'


# Grouping withdrawals for second and third approval
class WithdrawalBatch(models.Model):
    id = models.CharField(
        max_length=12,
        primary_key=True,
        editable=False,
        unique=True
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=False,
        blank=False
    )
    scheme = models.ForeignKey(
        InvestmentScheme,
        on_delete=models.CASCADE,
        null=False,
        blank=False
    )
    bank = models.ForeignKey(
        BankAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='withdrawal_batch'
    )
    payment_method_choices = [
        ('Mobile Money', 'Mobile Money'),
        ('Bank Transfer', 'Bank Transfer'),
        ('cheque','Cheque')
    ]
    mode_of_payment = models.CharField(
        max_length=255,
        default='',
        null=True,
        choices=payment_method_choices
    )
    date_created = models.DateTimeField(
        auto_now_add=True
    )
    last_updated = models.DateTimeField(
        auto_now=True
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
    # dynamic file path for document uploads
    def upload_file(self,filename):
        tenant_name = self.tenant.name
        # user_name = self.member.user.username

        return os.path.join('File_uploads',tenant_name,'BATCH_UPLOADS',filename)
    bank_file = models.FileField(
        null=True,
        blank=True,
        upload_to=upload_file,
        validators=[FileExtensionValidator(allowed_extensions=['xls','xlsx'])]
    )

    class Meta:
        verbose_name = 'Batch Withdrawal'

    def __str__(self):
        return f'Batch Withdrawal Object | {self.tenant} | {self.scheme} - {self.id}'
    
    @property
    def total_amount(self):
        withdrawals = self.withdrawal_request.all()
        total = Decimal(0)
        if withdrawals:
            for w in withdrawals:
                total += w.amount
        return total

    # approve individual request from batch withdrawal
    def approve_batch(self,approval_level):
        if approval_level not in [1,2,3,4]:
            raise ValueError('Invalid approval level, must be 1,2,3, or 4')
        try:
            with transaction.atomic():
                if approval_level == 1 and not self.first_approval:
                    # Update individal withdrawal requests
                    self.withdrawal_request.filter(first_approval=False).update(first_approval=True)
                    # Update batch
                    self.first_approval = True
                elif approval_level == 2 and not self.second_approval:
                    self.withdrawal_request.filter(second_approval=False).update(second_approval=True)
                    self.second_approval = True
                elif approval_level == 3 and not self.third_approval:
                    self.withdrawal_request.filter(third_approval=False).update(third_approval=True)
                    self.third_approval = True
                elif approval_level == 4 and not self.fourth_approval:
                    self.withdrawal_request.filter(fourth_approval=False).update(fourth_approval=True)
                    self.fourth_approval = True
                else:
                    raise ValueError('Approval level has already been processed')
                
                self.save()
                return {
                    'status':'success',
                    'message':f'Withdrawal batch approved for level {approval_level}.'
                }
        except Exception as e:
            return {
                'status':'error',
                'message':f'An error occured trying to approve: {str(e)}'
            }
    
    def save(self,*args,**kwargs):
        if not self.id:
            self.id = generate_short_alpha_numeric_id(WithdrawalBatch)
        return super().save(*args,**kwargs)
        

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

