from django.db import models
from django.urls import reverse

# Create your models here.

class InvestmentDetail(models.Model):
    investment_type = models.CharField(max_length=50)
    account_type = models.CharField(max_length=50)
    account_name = models.CharField(max_length=50)
    account_number = models.IntegerField(unique=True)
    principal_amount = models.FloatField()
    interest_percentage = models.FloatField()
    # Rollover percentage interest
    rollover_interest_percentage = models.FloatField(null=True, blank=True)

    interest_amount = models.FloatField(blank=True, null=True)
    interest_start_date = models.DateField(null=False, blank=False)
    interest_end_date = models.DateField(null=False, blank=False)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    CHOICES = [('ROLLOVER','Roll Over'),('END','End'),('NULL', 'null')]
    roll_over = models.CharField(choices=CHOICES, default='NULL', max_length=15)
    


    # calculates the tenure of investment
    def calculate_tenure(self):
        return (self.interest_end_date - self.interest_start_date).days
    
    # serves as a property to self
    @property
    def tenure(self):
        print('calculating tenure')
        return self.calculate_tenure()
    
    # Roll over Principal Calculation
    def calculate_rollover_principal(self):
        return (self.principal_amount+ self.interest_amount)
    
    @property
    def rollover_principal(self):
        print('calculating rollover principal')
        return self.calculate_rollover_principal()
    

    # Rollover accumulated amount
    def calculate_rollover_accumulated_amount(self):
        if self.rollover_interest_percentage is None or self.rollover_principal is None:
            return 0
        return (((self.rollover_interest_percentage/100.0)*(self.rollover_principal))+ self.rollover_principal)
    
    @property
    def rollover_accumulated_amount(self):
        print('calculating rollover amount')
        return self.calculate_rollover_accumulated_amount()


    def __str__(self):
        return f'{self.account_name}\'s account'
    
    def get_absolute_url(self):
        return reverse('investment_detail', kwargs={'pk':self.pk}) 
    

class Member(models.Model):
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    staff_id = models.PositiveIntegerField(unique=True)
    total_amount_to_date = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    profit = models.DecimalField(max_digits=10, decimal_places=2,blank=True, null=True)
    status = models.CharField(max_length=20,blank=True, null=True)
    subscription_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.first_name} {self.last_name}\'s account'
    
    def get_absolute_url(self):
        return reverse('member_detail', kwargs={'pk':self.pk})