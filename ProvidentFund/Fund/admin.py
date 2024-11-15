from django.contrib import admin
from Fund.models import InvestmentDetail,BankInterest,DelayedInterest,AuditTrail,BankInterestRate

# Register your models here.



class InvestmentDetailAdmin(admin.ModelAdmin):
    list_display=('invoice_number','account_name','account_type','status','investment_type','account_number','principal_amount','interest_amount','interest_start_date','interest_end_date','interest_percentage','tenure','remaining_days','rollover_principal','rollover_accumulated_amount','rollover_interest_percentage')


    readonly_fields = ('interest_amount','invoice_number','rollover_interest_percentage','created_date')


admin.site.register(InvestmentDetail, InvestmentDetailAdmin)

# class MemberAdmin(admin.ModelAdmin):
#     readonly_fields = ('profit',)
#     list_display = ('first_name','last_name','total_amount_to_date','profit','status')

# admin.site.register(Member,MemberAdmin)

admin.site.register(BankInterest)
admin.site.register(DelayedInterest)
admin.site.register(AuditTrail)
admin.site.register(BankInterestRate)