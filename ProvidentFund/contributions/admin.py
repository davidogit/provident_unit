from django.contrib import admin
from .models import ContributionsDetail, StaffAPI, StaffMember, GeneralLedger


admin.site.register(ContributionsDetail)

admin.site.register(StaffMember)

admin.site.register(GeneralLedger)

admin.site.register(StaffAPI)
