from django.db import models

# Create your models here.

class InvestmentDetail(models.Model):
    investment_type = models.CharField(max_length=50)
    account_type = models.CharField(max_length=50)
    account_name = models.CharField(max_length=50)
    account_number = models.IntegerField(unique=True)
    principal_amount = models.DecimalField(decimal_places=2, max_digits=10)
    interest_percentage = models.IntegerField()
    interest_amount = models.DecimalField(decimal_places=2, max_digits=10)
    interest_start_date = models.DateTimeField()
    interest_end_date = models.DateTimeField()
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.account_name}\'s account'
    

class Member(models.Model):
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    staff_id = models.PositiveIntegerField(unique=True)
    total_amount_to_date = models.DecimalField(max_digits=10, decimal_places=2)
    profit = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20)
    subscription_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.first_name} {self.last_name}\'s account'