from django.db import models
from django.urls import reverse
from django.utils import timezone

# Create your models here.

class ContributionsDetail(models.Model):
    EmployeeNo = models.PositiveIntegerField(primary_key=True)
    Fundtype = models.IntegerField()
    EmployeeAmount = models.FloatField()
    EmployerAmount = models.FloatField()
    RetroEmployeeAmount = models.FloatField()
    RetroEmployerAmount = models.FloatField()
    Employee55Amount = models.FloatField()
    Employer55Amount = models.FloatField() 
    RetroEmployee55Amount = models.FloatField()
    RetroEmployer55Amount = models.FloatField()
    ContributionDate = models.DateTimeField( auto_now_add=True)
    CreatedDate = models.DateTimeField( auto_now_add=True)
    UpdatedDate =  models.DateTimeField( auto_now=True) 


def __str__(self):
        return f"Contribution by Employee {self.EmployeeNo}"

def get_absolute_url(self):
        return reverse('contributions_detail', kwargs={'pk':self.pk})





class StaffMember(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('separated', 'Separated'),
    ]

    full_name = models.CharField(max_length=255)
    staff_number = models.CharField(max_length=100, unique=True)
    date_joined = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

def __str__(self):
        return self.full_name
    
# def get_absolute_url(self):
#         return reverse('StaffMember', kwargs={'pk':self.pk})


class GeneralLedger(models.Model):
    staff_member = models.ForeignKey(StaffMember, on_delete=models.CASCADE , related_name="staff_members")
    gl_date = models.DateField(default=timezone.now)
    total_contributions_a = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_contributions_b = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_contributions_c = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_contributions_d = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_interest = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_payments = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

@property
def net_balance(self):
        contributions = (
            self.total_contributions_a + 
            self.total_contributions_b + 
            self.total_contributions_c + 
            self.total_contributions_d
        )
        return contributions + self.total_interest - self.total_payments
def __str__(self):
        return f"GL Entry for {self.staff_member.full_name} on {self.gl_date}"

def get_absolute_url(self):
        return reverse('GeneralLedger', kwargs={'pk':self.pk})


        

# Temporary Staff Model For API test

# import uuid


# class IntegerUUIDField(models.Field):
#     description = "A field to store integer values as UUIDs"

#     def db_type(self, connection):
#         return 'bigint'  # Assuming you want to use bigint for storing large integers

#     def from_db_value(self, value, expression, connection):
#         if value is None:
#             return value
#         return str(value)  # Convert integer to string

#     def to_python(self, value):
#         if isinstance(value, int):
#             return value
#         elif isinstance(value, str):
#             return int(value)
#         return value

#     def get_prep_value(self, value):
#         return int(value) if value is not None else None

# # Example model using IntegerUUIDField
#     # Other fields...

class StaffAPI(models.Model):
    Id = models.BigIntegerField(primary_key=True)
    Fullname = models.CharField(max_length=255)
    Staffnumber = models.IntegerField()
    Datejoined = models.DateTimeField(auto_now=True)
    status =  models.IntegerField()
    Fundtype = models.CharField(max_length=50)
    EmployeeAmount = models.DecimalField(max_digits=10, decimal_places=2)
    EmployerAmount = models.DecimalField(max_digits=10, decimal_places=2)
    RetroEmployeeAmount = models.DecimalField(max_digits=10, decimal_places=2)
    RetroEmployerAmount = models.DecimalField(max_digits=10, decimal_places=2)
    Employee55Amount = models.DecimalField(max_digits=10, decimal_places=2)
    Employer55Amount = models.DecimalField(max_digits=10, decimal_places=2)
    RetroEmployee55Amount = models.DecimalField(max_digits=10, decimal_places=2)
    RetroEmployer55Amount = models.DecimalField(max_digits=10, decimal_places=2)
    ContributionDate = models.DateTimeField(auto_now=True)
    
    
    def __str__(self):
        return self.Fullname