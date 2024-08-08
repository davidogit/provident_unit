from django.db import models
from MultiScheme.models import InvestmentScheme
# from django.utils import timezone

class StaffAPI(models.Model):
    investment_scheme = models.ForeignKey(InvestmentScheme, on_delete=models.CASCADE, null=True)
    Id = models.BigIntegerField(primary_key=True, unique=True)
    first_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    staff_number = models.IntegerField()
    date_joined = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, blank=True, null=True, default='active')
    fund_type = models.CharField(max_length=50)
    _amount = models.FloatField(null=True,blank=True,default=0.00)
    exited_date = models.DateTimeField(null=True, blank=True)
    exited_flag = models.BooleanField(default=False)
    profit = models.FloatField(default=0.0)
    subscription_date = models.DateField()
    updated_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.last_name

    # @property
    # def contributions(self):
    #     return self.contribution_set.all()
    
    @property
    def amount(self):
        return self._amount
    
    @amount.setter
    def amount(self,value):
        self._amount += value


class Contribution(models.Model):
    # tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True)
    investment_scheme = models.ForeignKey(InvestmentScheme, on_delete=models.CASCADE, null=True)
    member = models.ForeignKey(StaffAPI, on_delete=models.CASCADE, related_name='contributions')
    month = models.CharField(max_length=20)
    year = models.CharField(max_length=4)
    employee_amount = models.FloatField()
    employer_amount = models.FloatField()
    retro_employee_amount = models.FloatField()
    retro_employer_amount = models.FloatField()
    contribution_date = models.DateTimeField()

    def calculated_total_contributions(self):
        a = self.employee_amount
        b = self.employer_amount
        c = self.retro_employee_amount
        d = self.retro_employer_amount
        
        return (a + b + c + d)

    @property
    def total_contributions(self):
        return self.calculated_total_contributions()

    def __str__(self):
        return f"{self.member.last_name}'s - {self.month} {self.year}"
    

    # Saving every contribution for user whenever a contribution is made
    def save(self, *args, **kwargs):

        super().save(*args,**kwargs)

        # update member.amount field
        self.member.amount = self.total_contributions
        self.member.save()
