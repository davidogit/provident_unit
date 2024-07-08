from django.contrib import admin
from .models import  StaffAPI, Contribution

class StaffAPIAdmin(admin.ModelAdmin):
    readonly_fields = (
        'Id',
        'Fullname',
        'Staffnumber',
        'Datejoined',
        'status',
        'Fundtype',
        'EmployeeAmount',
        'EmployerAmount',
        'RetroEmployeeAmount',
        'RetroEmployerAmount',
        'ContributionDate',
        'ExitedDate',
        # 'ExitedFlag',
    )


admin.site.register(StaffAPI,StaffAPIAdmin)


admin.site.register(Contribution)


