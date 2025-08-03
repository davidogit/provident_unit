from django.db import models
from MultiScheme.models import Tenant
from ProvidentFund.settings import AUTH_USER_MODEL


# Create your models here.

class ApprovalActionType(models.TextChoices):
    LOAN_APPROVAL = "LOAN_APPROVAL", "Loan Approval"
    LOAN_TOPUP_APPROVAL = "LOAN_TOPUP_APPROVAL", "Loan Topup Approval"
    WITHDRAWAL_APPROVAL = "WITHDRAWAL_APPROVAL", "Withdrawal Approval"
    INVESTMENT_APPROVAL = "INVESTMENT_APPROVAL", "Investment Approval"
    REQUISITION_APPROVAL = "REQUISITION_APPROVAL", "Requisition Approval"

class RoleType(models.TextChoices):
    ADMIN = "Admin", "Admin"
    MEMBER = "Member", "Member"
    CONTRIBUTION_MANAGER = "Contribution Manager", "Contribution Manager"
    CONTRIBUTION_ANALYST = "Contribution Analyst", "Contribution Analyst"
    CONTRIBUTION_SUPERVISOR = "Contribution Supervisor", "Contribution Supervisor"
    FINANCE_MANAGER = "Finance Manager", "Finance Manager"
    FINANCE_ANALYST = "Finance Analyst", "Finance Analyst"
    FINANCE_SUPERVISOR = "Finance Supervisor", "Finance Supervisor"
    SCHEME_MANAGER = "Scheme Manager", "Scheme Manager"
    SCHEME_ANALYST = "Scheme Analyst", "Scheme Analyst"
    SCHEME_SUPERVISOR = "Scheme Supervisor", "Scheme Supervisor"
    TREASURY_MANAGER = "Treasury Manager", "Treasury Manager"
    TREASURY_ANALYST = "Treasury Analyst", "Treasury Analyst"
    TREASURY_SUPERVISOR = "Treasury Supervisor", "Treasury Supervisor"
    SUPER_USER = "Super User", "Super User"

#     TODO: complete the roles


class ApprovalWorkflow(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='approval_workflows'
    )
    name = models.CharField(
        max_length=100,
        null=False,
        blank=False
    )
    action_type = models.CharField(
        max_length=50,
        choices=ApprovalActionType.choices
    )
    is_active = models.BooleanField(
        default=True
    )
    created_date = models.DateTimeField(
        auto_now_add=True
    )
    updated_date = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f'{self.tenant.name} - {self.get_action_type_display()}'



class WorkflowStep(models.Model):
    workflow = models.ForeignKey(
        ApprovalWorkflow,
        on_delete=models.CASCADE,
        related_name='steps'
    )
    order = models.PositiveIntegerField(
        help_text="Order of the step in the workflow. Steps with same order can run in parallel."
    )
    role = models.CharField(
        max_length=50,
        choices=RoleType.choices,
        help_text="Role of the user assigned to the step."
    )
    required_approvals = models.PositiveIntegerField(
        help_text="Number of approvals required for the step to be considered completed.",
        default=1
    )
    is_optional = models.BooleanField(
        default=False,
        help_text="Whether the step is optional or not."
    )

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'Step {self.order} - {self.workflow.name} - {self.get_role_display()}'



class ApprovalInstance(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='approval_instances'
    )
    workflow = models.ForeignKey(
        ApprovalWorkflow,
        on_delete=models.CASCADE,
        related_name='instances'
    )
    action_type = models.CharField(
        max_length=50,
        choices=ApprovalActionType.choices
    )
    target_object_type = models.CharField(
        max_length=100,
        help_text="Type of the object being approved."
    )
    target_object_id = models.PositiveIntegerField(
        help_text="ID of the object being approved."
    )
    current_step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='current_instances',
        help_text="Current step of the approval instance."
    )
    status = models.CharField(
        max_length=50,
        choices=[
            ('PENDING', 'Pending'),
            ('APPROVED', 'Approved'),
            ('REJECTED', 'Rejected')
        ],
        default='PENDING'
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )
    finalized_at = models.DateTimeField(
        null=True,
        blank=True
    )


    def __str__(self):
        return f'{self.action_type} - Approval for {self.workflow.name} - {self.target_object_type} #{self.target_object_id}'



class ApprovalLog(models.Model):
    instance = models.ForeignKey(
        ApprovalInstance,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    user = models.ForeignKey(
        AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='approval_logs'
    )
    action = models.CharField(
        max_length=50,
        choices=[
            ('APPROVED', 'Approved'),
            ('REJECTED', 'Rejected')
        ]
    )
    comment = models.TextField(
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )


    class Meta:
        unique_together = ('instance', 'step', 'user')

    def __str__(self):
        return f'{self.user.username} - {self.action} Step-{self.step.order} - {self.instance.workflow.name} - {self.instance.target_object_type} #{self.instance.target_object_id}'