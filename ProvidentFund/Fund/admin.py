from django.contrib import admin
from Fund.models import InvestmentDetail

# Register your models here.



class InvestmentAdmin(admin.ModelAdmin):
    readonly_fields = ('account_name','account_type','account_number','principal_amount','interest_amount','interest_start_date','interest_end_date','interest_percentage')

admin.site.register(InvestmentDetail,InvestmentAdmin)