from django.contrib import admin
from .models import ContributionsDetail, StaffAPI



# # Register your models here.

# admin.py

# from django.contrib import admin
# from .models import ContributionsDetails

# @admin.register(ContributionsDetails)
# class ContributionAdmin(admin.ModelAdmin):
#     list_display = ('Id', 'EmployeeNo', 'FundType', 'EmployeeAmount', 'EmployerAmount', 'ContributionDate')
#     search_fields = ('EmployeeNo', 'FundType')



admin.site.register(ContributionsDetail)

from django.contrib import admin
from .models import StaffMember, GeneralLedger


admin.site.register(StaffMember)

admin.site.register(GeneralLedger)
admin.site.register(StaffAPI)

# @admin.register(StaffMember)
# class StaffMemberAdmin(admin.ModelAdmin):
#     list_display = ('full_name', 'staff_number', 'date_joined', 'status')
#     search_fields = ('full_name', 'staff_number')
#     list_filter = ('status', 'date_joined')

# @admin.register(GeneralLedger)
# class GeneralLedgerAdmin(admin.ModelAdmin):
#     # list_display = ('staff_member', 'gl_date', 'total_contributions_a', 'total_contributions_b', 'total_contributions_c', 'total_contributions_d', 'total_interest', 'total_payments', 'net_balance')
#     search_fields = ('staff_member__full_name', 'staff_member__staff_number')
#     list_filter = ('gl_date',)
#     # readonly_fields = ('net_balance',)