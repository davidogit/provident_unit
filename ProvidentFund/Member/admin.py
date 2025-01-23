from django.contrib import admin
from Member.models import Member,SchemeApproval,Transaction,ExitApproval,WithdrawalRequest
# Register your models here.
admin.site.register(Member)
admin.site.register(SchemeApproval)
admin.site.register(ExitApproval)
admin.site.register(Transaction)
admin.site.register(WithdrawalRequest)