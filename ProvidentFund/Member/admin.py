from django.contrib import admin
from Member.models import Member,SchemeApproval,TransactionHistory,ExitApproval,WithdrawalRequest
# Register your models here.
admin.site.register(Member)
admin.site.register(SchemeApproval)
admin.site.register(ExitApproval)
admin.site.register(TransactionHistory)
admin.site.register(WithdrawalRequest)