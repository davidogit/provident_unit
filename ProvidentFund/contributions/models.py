from django.db import models
from django.urls import reverse
from django.utils import timezone

# Create your models here.
class StaffAPI(models.Model):
    Id = models.BigIntegerField(primary_key=True, unique=True)
    Fullname = models.CharField(max_length=255)
    Staffnumber = models.IntegerField()
    Datejoined = models.DateTimeField(auto_now=True)
    status = models.IntegerField()
    Fundtype = models.CharField(max_length=50)
    EmployeeAmount = models.FloatField()
    EmployerAmount = models.FloatField()
    RetroEmployeeAmount = models.FloatField()
    RetroEmployerAmount = models.FloatField()
    ContributionDate = models.DateTimeField(auto_now=True)
    ExitedDate = models.DateTimeField(null=True, blank=True)
    ExitedFlag = models.BooleanField(default=False)

    def __str__(self):
        return self.Fullname

    @property
    def contributions(self):
        return self.contribution_set.all()

    @property
    def total_contributions(self):
        total = self.contributions.aggregate(
            total=models.Sum(
                models.F('EmployeeAmount') + 
                models.F('EmployerAmount') + 
                models.F('RetroEmployeeAmount') + 
                models.F('RetroEmployerAmount')
            )
        )['total'] or 0
        return total

class Contribution(models.Model):
    member = models.ForeignKey(StaffAPI, on_delete=models.CASCADE, related_name='contributions')
    month = models.CharField(max_length=20)
    year = models.CharField(max_length=4)
    EmployeeAmount = models.FloatField()
    EmployerAmount = models.FloatField()
    RetroEmployeeAmount = models.FloatField()
    RetroEmployerAmount = models.FloatField()
    ContributionDate = models.DateTimeField()

    def calculated_total_contributions(self):
        a = self.EmployeeAmount
        b = self.EmployerAmount 
        c = self.RetroEmployeeAmount
        d = self.RetroEmployerAmount
        
        results = a+b+c+d
        
        return results

    @property
    def total_contributions(self):
        return self.calculated_total_contributions()

    def __str__(self):
        return f'{self.member.Fullname} - {self.month} {self.year}'
