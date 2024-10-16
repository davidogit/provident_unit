from django.contrib import admin
from .models import Tenant,InvestmentScheme
# from simple_history.admin import SimpleHistoryAdmin
# Register your models here.




class InvestmentAdmin(admin.ModelAdmin):
    readonly_fields = ('id',)
    list_display = ('id','name','created_date','updated_date')


# class InvestmenSchemeHistory(SimpleHistoryAdmin):
#     list_display = ['id', 'name']
#     # history_list_display = ['status']
#     search_fields = ['name', 'user__username']
admin.site.register(InvestmentScheme)


class TenantAdmin(admin.ModelAdmin):
    readonly_fields = ('id',)
admin.site.register(Tenant,TenantAdmin)