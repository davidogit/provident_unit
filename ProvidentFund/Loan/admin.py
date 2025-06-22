from django.contrib import admin
from .models import LoanApplication, LoanType, LoanRepayment, LoanAccountMapping, LoanAmortizationSchedule, LoanTopUp

# Register your models here.

admin.site.register(LoanApplication)
admin.site.register(LoanRepayment)
admin.site.register(LoanType)
admin.site.register(LoanAccountMapping)
admin.site.register(LoanAmortizationSchedule)
admin.site.register(LoanTopUp)