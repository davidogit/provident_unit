from django.db import models
from django.urls import reverse

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