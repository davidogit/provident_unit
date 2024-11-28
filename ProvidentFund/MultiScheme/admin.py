from django.contrib import admin
from .models import Tenant,InvestmentScheme,SchemeSettings
# from simple_history.admin import SimpleHistoryAdmin
# Register your models here.




class InvestmentAdmin(admin.ModelAdmin):
    readonly_fields = ('id',)
    list_display = ('id','name','created_date','updated_date')


admin.site.register(InvestmentScheme,InvestmentAdmin)


class TenantAdmin(admin.ModelAdmin):
    readonly_fields = ('id',)
admin.site.register(Tenant,TenantAdmin)

admin.site.register(SchemeSettings)