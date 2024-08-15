from django.contrib import admin
from .models import Tenant,InvestmentScheme
# Register your models here.

admin.site.register(Tenant)


class InvestmentAdmin(admin.ModelAdmin):
    readonly_fields = ('id',)
    list_display = ('id','name','created_date','updated_date')
admin.site.register(InvestmentScheme,InvestmentAdmin)