from django.contrib import admin
from .models import ApprovalWorkflow,ApprovalLog,ApprovalInstance,WorkflowStep
# Register your models here.

admin.site.register(ApprovalWorkflow)
admin.site.register(ApprovalLog)
admin.site.register(ApprovalInstance)
admin.site.register(WorkflowStep)
