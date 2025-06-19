from django.contrib import admin
from .models import LoanApplication, LoanType, LoanRepayment, LoanAccountMapping, LoanAmortizationSchedule

# Register your models here.

admin.site.register(LoanApplication)
admin.site.register(LoanRepayment)
admin.site.register(LoanType)
admin.site.register(LoanAccountMapping)
admin.site.register(LoanAmortizationSchedule)