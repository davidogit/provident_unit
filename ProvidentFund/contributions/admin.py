from django.contrib import admin
from .models import ContributionsDetail


# # Register your models here.

# admin.py

# from django.contrib import admin
# from .models import ContributionsDetails

# @admin.register(ContributionsDetails)
# class ContributionAdmin(admin.ModelAdmin):
#     list_display = ('Id', 'EmployeeNo', 'FundType', 'EmployeeAmount', 'EmployerAmount', 'ContributionDate')
#     search_fields = ('EmployeeNo', 'FundType')



admin.site.register(ContributionsDetail)