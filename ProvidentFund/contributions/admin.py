from django.contrib import admin
from .models import  StaffAPI, Contribution

class StaffAPIAdmin(admin.ModelAdmin):
    readonly_fields = (
        'Id',
        'first_name',
        'last_name',
        'staff_number',
        'date_joined',
        'status',
        'fund_type',
        # 'employee_amount',
        # 'employer_amount',
        # 'retro_employee_amount',
        # 'retro_employer_amount',
        # 'contribution_date',
        'exited_date',
        # 'exited_flag',
        'profit',
        # 'subscription_date',
        'updated_date',

    )


admin.site.register(StaffAPI,StaffAPIAdmin)


admin.site.register(Contribution)


