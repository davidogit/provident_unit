from django import forms
from .models import ApprovalWorkflow, WorkflowStep

class ApprovalWorkflowForm(forms.ModelForm):
    class Meta:
        model = ApprovalWorkflow
        fields = ('name', 'action_type', 'is_active')


class WorkflowStepForm(forms.ModelForm):
    class Meta:
        model = WorkflowStep
        fields = ('order', 'role', 'required_approvals')