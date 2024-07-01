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
        'Employee55Amount',
        'Employer55Amount',
        'RetroEmployee55Amount',
        'RetroEmployer55Amount',
        'ContributionDate',
        'ExitedDate',
        'ExitedFlag',
    )


admin.site.register(StaffAPI,StaffAPIAdmin)


admin.site.register(Contribution)


