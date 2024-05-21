from django.db import models

# Create your models here.

class InvestmentDetail(models.Model):
    account_type = models.CharField(max_length=50)
    account_name = models.CharField(max_length=50)
    account_number = models.IntegerField(unique=True)
    principal_amount = models.DecimalField(decimal_places=2, max_digits=100)
    interest_percentage = models.IntegerField()
    interest_amount = models.DecimalField(decimal_places=2, max_digits=100)
    interest_start_date = models.DateTimeField()
    interest_end_date = models.DateTimeField()
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.account_name}\'s account'