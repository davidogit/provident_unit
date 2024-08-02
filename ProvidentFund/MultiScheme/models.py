from django.db import models
import uuid

# Create your models here.

# Tenanat model

class Tenant(models.Model):
    id = models.IntegerField(primary_key=True, default='', editable=True)
    name =  models.CharField(max_length=50, null=True, blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name}\'s Account'


# Schemes model

class InvestmentScheme(models.Model):
    id = models.IntegerField(primary_key=True, default='', editable=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='investment_schemes',null=True)
    name = models.CharField(max_length=50,null=True)
    description = models.TextField(blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)


    def __str__(self):
        return f'{self.name} Scheme'