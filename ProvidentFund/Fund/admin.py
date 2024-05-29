from django.contrib import admin
from Fund.models import InvestmentDetail,Member

# Register your models here.



# class InvestmentAdmin(admin.ModelAdmin):
#     readonly_fields = ('account_name','account_type','account_number','principal_amount','interest_amount','interest_start_date','interest_end_date','interest_percentage')

admin.site.register(InvestmentDetail)

class MemberAdmin(admin.ModelAdmin):
    readonly_fields = ('profit',)

admin.site.register(Member,MemberAdmin)