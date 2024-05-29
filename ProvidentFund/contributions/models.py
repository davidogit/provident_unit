from django.db import models
from django.urls import reverse

# Create your models here.

class ContributionsDetail(models.Model):
    EmployeeNo = models.PositiveIntegerField(primary_key=True)
    Fundtype = models.IntegerField()
    EmployeeAmount = models.PositiveIntegerField()
    EmployerAmount = models.PositiveIntegerField()
    RetroEmployeeAmount = models.PositiveIntegerField()
    RetroEmployerAmount = models.PositiveIntegerField()
    Employee55Amount = models.PositiveIntegerField()
    Employer55Amount = models.PositiveIntegerField() 
    RetroEmployee55Amount = models.PositiveIntegerField()
    RetroEmployer55Amount = models.PositiveIntegerField()
    ContributionDate = models.DateTimeField( auto_now_add=True)
    CreatedDate = models.DateTimeField( auto_now_add=True)
    UpdatedDate =  models.DateTimeField( auto_now_add=True) 


def __str__(self):
        return f"Contribution by Employee {self.EmployeeNo}"

def get_absolute_url(self):
        return reverse('contributions_detail', kwargs={'pk':self.pk})