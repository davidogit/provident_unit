import os
from django.db import models
from django.contrib.auth.models import User
from MultiScheme.models import Tenant
from django.conf import settings

from contributions.models import StaffAPI
from MultiScheme.models import InvestmentScheme
from django.utils import timezone
from django.core.validators import FileExtensionValidator

# Create your models here.

class Member(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE,null=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='member')
    staff_id = models.PositiveIntegerField(unique=True, null=True, blank=False)
    tel_number = models.PositiveIntegerField()

    address = models.CharField(max_length=50, blank=True,null=True)
    date_of_birth = models.DateField( auto_now=False, auto_now_add=False, null=True)
    nationality = models.CharField(max_length = 50,blank=True, null=True)
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
    investment_scheme = models.ForeignKey(InvestmentScheme, on_delete=models.CASCADE, null=True, blank=True)


    def __str__(self):
        return f'{self.user.username}\'s account'
    

    # dynamic file path for document uploads
    def upload_image(self,filename):
        tenant_name = self.tenant.name
        user_name = self.user.username

        return os.path.join('File_uploads',tenant_name,user_name,filename)

    image = models.ImageField(upload_to=upload_image, blank=True, null=True,default='profile_images/default_profile_pic.png')





# SCHEME APPLICATION MODEL
class SchemeApproval(models.Model):
    
    tenant = models.ForeignKey(Tenant,on_delete=models.CASCADE)
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    staff = models.ForeignKey(StaffAPI, on_delete=models.CASCADE)
    scheme = models.ForeignKey(InvestmentScheme, on_delete=models.CASCADE)
    # applied_date = models.DateTimeField(auto_now_add=True)
    approval_date = models.DateTimeField(null=True,blank=True)
    application_date = models.DateTimeField(null=True,blank=True)
    approved_by_hr = models.BooleanField(default=False)


    # dynamic file path for document uploads
    def upload_file(self,filename):
        tenant_name = self.tenant.name
        user_name = self.member.user.username

        return os.path.join('File_uploads',tenant_name,user_name,filename)


    document = models.FileField(blank=True,null=True, upload_to=upload_file, validators=[FileExtensionValidator(allowed_extensions=['pdf','docx'])])


    # method to approve scheme applications
    def approve(self):
        self.approved_by_hr = True
        self.approval_date = timezone.now()
        self.save()

        # Add member to scheme(but in this case we have to set it on the StaffApi model)
        self.staff.investment_scheme.add(self.scheme)


class ExitApproval(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    staff = models.ForeignKey(StaffAPI, on_delete=models.CASCADE)
    scheme = models.ForeignKey(InvestmentScheme,on_delete=models.CASCADE)
    reason = models.CharField(max_length=500, default='')
    application_date = models.DateTimeField(auto_now_add=True,null=False,blank=True)
    approval_date = models.DateTimeField(null=True,blank=True)
    approved = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.tenant.name} - {self.member.user.username}\'s EXIT application'
