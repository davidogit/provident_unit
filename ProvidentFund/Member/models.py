from django.db import models
from django.contrib.auth.models import User
from MultiScheme.models import Tenant
from django.conf import settings

from contributions.models import StaffAPI
from MultiScheme.models import InvestmentScheme
from django.utils import timezone

# Create your models here.

class Member(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE,null=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='member')
    staff_id = models.PositiveIntegerField(unique=True, null=False, blank=False)
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

    scheme_approval = models.BooleanField(default=False)
    registration_date = models.DateTimeField(auto_now_add=True, null=True)

    


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

    # method to approve scheme applications
    def approve(self):
        self.approved_by_hr = True
        self.approval_date = timezone.now()
        self.save()

        # Add member to scheme(but in this case we have to set it on the StaffApi model)
        self.staff.investment_scheme.add(self.scheme)