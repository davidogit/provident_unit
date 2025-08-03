import logging

from django.db import transaction
from django.utils import timezone
from django.apps import apps

from ProvidentFund.settings import AUTH_USER_MODEL
from approval_workflow.models import WorkflowStep
from .models import ApprovalWorkflow, ApprovalInstance, ApprovalLog
from MultiScheme.models import Tenant
from notification.tasks import send_approval_email_to_next_step_users

logger = logging.getLogger(__name__)


def check_duplicate_action(user: 'AUTH_USER_MODEL', instance: 'ApprovalInstance', step: 'WorkflowStep'):
    print(f"Checking for duplicate actions for user {user.username} in step {step.order} of workflow {instance.workflow.name}")
    print(ApprovalLog.objects.filter(instance=instance,step=step,user=user).exists())
    if ApprovalLog.objects.filter(instance=instance,step=step,user=user).exists():
        print(f"User {user.username} has already taken action in step {step.order} of workflow {instance.workflow.name}")
        raise ValueError(f"User {user.username} has already taken action in step {step.order} of workflow {instance.workflow.name}")


def validate_user_role(user: 'AUTH_USER_MODEL', step: 'WorkflowStep'):
    if not step:
        raise ValueError("No approval step defined for this workflow")
    if not user.groups.filter(name=step.role).exists():
        raise PermissionError(f"User {user.username} does not have the required role {step.role} to approve this action")


class ApprovalWorkflowEngine:
    def __init__(self,tenant: 'Tenant', target_object, action_type: str):
        self.tenant = tenant
        self.target = target_object
        self.action_type = action_type


    def start_workflow(self):
        # Check if there's already an existing instance for target and action
        existing_instance = ApprovalInstance.objects.filter(
            tenant=self.tenant,
            target_object_type=self.target.__class__.__name__,
            target_object_id=self.target.id,
            action_type=self.action_type,
            status='PENDING'
        ).first()

        if existing_instance:
            return existing_instance

        # If there is no instance for target and action, then proceed to create a new instance out of the workflow
        workflow = ApprovalWorkflow.objects.filter(
            tenant=self.tenant,
            action_type=self.action_type,
            is_active=True
        ).first()

        if not workflow:
            raise ValueError(f"No active workflow found for action {self.action_type}.")

        instance = ApprovalInstance.objects.create(
            tenant=self.tenant,
            workflow=workflow,
            action_type=self.action_type,
            target_object_type=self.target.__class__.__name__,
            target_object_id=self.target.id,
            current_step=workflow.steps.first(),
            status='PENDING'
        )
        # Notify the first step approvers
        send_approval_email_to_next_step_users.delay(instance.id)
        return instance


    def approve(self, user: 'AUTH_USER_MODEL', instance_id: int, comment: str = "", **kwargs):
        with transaction.atomic():
            instance = ApprovalInstance.objects.select_related(
                "current_step",
                "workflow"
            ).get(id=instance_id)
            step = instance.current_step

            # validate user
            validate_user_role(user, step)
            # check for duplicate actions for a user
            logger.error(f"Checking for duplicate actions for user {user.username} in step {step.order} of workflow {instance.workflow.name} - 1")
            check_duplicate_action(user, instance, step)

            ApprovalLog.objects.create(
                instance=instance,
                step=step,
                user=user,
                action='APPROVED',
                comment=comment
            )

            kwargs.update({'comment':comment, 'user':user})
            # Proceed to finalize action if necessary
            self._advance_step(instance, step, **kwargs)


    def reject(self, user: 'AUTH_USER_MODEL', instance_id: int, comment: str = "", **kwargs):
        with transaction.atomic():
            instance = ApprovalInstance.objects.select_related(
                "current_step",
                "workflow"
            ).get(id=instance_id)
            step = instance.current_step

            # Validate user and check for duplicates
            validate_user_role(user, step)
            check_duplicate_action(user, instance, step)

            ApprovalLog.objects.create(
                instance=instance,
                step=step,
                user=user,
                action='REJECTED',
                comment=comment
            )

            # update status of workflow the instance
            instance.status = 'REJECTED'
            instance.finalized_at = timezone.now()
            instance.save()

            kwargs.update({'comment':comment, 'user':user})
            self._finalize(instance, approved=False, **kwargs)

    # HELPER METHODS

    def _advance_step(self, instance, step, **kwargs):
        approvals = ApprovalLog.objects.filter(
            instance=instance,
            step=step,
            action='APPROVED'
        ).count()

        if approvals >= step.required_approvals:
            next_step = instance.workflow.steps.filter(
                order__gt=step.order
            ).first()

            if next_step:
                instance.current_step = next_step
            #     Notify approvers of the next step if any
                send_approval_email_to_next_step_users.delay(instance.id)
            else:
                instance.status = 'APPROVED'
                instance.finalized_at = timezone.now()
                self._finalize(instance, approved=True,**kwargs)

        instance.save()

    def _finalize(self, instance, approved: 'bool', **kwargs):
        model_class = self._get_model_class(instance.target_object_type)
        obj = model_class.objects.get(id=instance.target_object_id)

        if approved:
        #     TODO: Ensure all models with approvals have approve and reject methods to handle model specific actions
            if hasattr(obj, 'approve'):
                obj.approve(**kwargs)
            else:
                logger.info(f"No approve method found for model {model_class.__name__}")
        else:
            if hasattr(obj, 'reject'):
                obj.reject(**kwargs)
            else:
                logger.info(f"No reject method found for model {model_class.__name__}")

    MODEL_APP_MAP = {
        'LoanApplication':'Loan',
        'LoanTopUp':'Loan',

        'InvestmentDetail':'Fund',
        'DelayedInterest':'Fund',
        'Requisition':'Fund',
        'ScheduledPaymentDates':'Fund',

        'Contribution':'contributions',

        'InvestmentScheme':'MultiScheme',
    }

    def _get_model_class(self, model_name: str):
        app_label = self.MODEL_APP_MAP.get(model_name, model_name)
        if not apps.is_installed(app_label):
            raise Exception(f"Model {model_name} is not installed")

        return apps.get_model(app_label, model_name)