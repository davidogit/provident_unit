from django.contrib import admin
from Member.models import Member,SchemeApproval,ExitApproval
# Register your models here.
admin.site.register(Member)
admin.site.register(SchemeApproval)
admin.site.register(ExitApproval)