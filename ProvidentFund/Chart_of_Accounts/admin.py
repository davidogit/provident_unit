from django.contrib import admin
from Chart_of_Accounts.models import ChartOfAccounts,AccountMapping,BankAccount,AccountParameters,AccountLedgerEntry
# Register your models here.

class ChartOfAccountsAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'parent',
        'account_code',
        'current_balance',
    )
admin.site.register(ChartOfAccounts,ChartOfAccountsAdmin)
admin.site.register(AccountMapping)
admin.site.register(BankAccount)
admin.site.register(AccountParameters)
admin.site.register(AccountLedgerEntry)