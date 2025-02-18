from django.contrib import admin
from Fund.models import InvestmentDetail,BankInterest,DelayedInterest,AuditTrail,BankInterestRate,Suppliers,Requisition,RequisitionItem,PurchaseOrder,PaymentInvoice,ScheduledPaymentDates

# Register your models here.



class InvestmentDetailAdmin(admin.ModelAdmin):
    list_display=('invoice_number','account_name','account_type','status','investment_type','account_number','principal_amount','interest_amount','interest_start_date','interest_end_date','interest_percentage','tenure','remaining_days')


    readonly_fields = ('interest_amount','invoice_number','created_date')


admin.site.register(InvestmentDetail, InvestmentDetailAdmin)

# class MemberAdmin(admin.ModelAdmin):
#     readonly_fields = ('profit',)
#     list_display = ('first_name','last_name','total_amount_to_date','profit','status')

# admin.site.register(Member,MemberAdmin)

admin.site.register(BankInterest)
class DelayedInterestAdmin(admin.ModelAdmin):
    list_display=('invoice_number','principal','status','date_paid','approved','approved_by')


    readonly_fields = ('invoice_number','created_date','principal','status','rate_d_int','date_paid','approved_by')
admin.site.register(DelayedInterest,DelayedInterestAdmin)
admin.site.register(AuditTrail)
admin.site.register(BankInterestRate)
admin.site.register(Suppliers)
admin.site.register(Requisition)
admin.site.register(RequisitionItem)
admin.site.register(PurchaseOrder)
admin.site.register(PaymentInvoice)
admin.site.register(ScheduledPaymentDates)