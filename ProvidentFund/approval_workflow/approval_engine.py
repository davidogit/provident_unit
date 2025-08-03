import logging

from django.db import transaction
from django.utils import timezone
from django.apps import apps

from ProvidentFund.settings import AUTH_USER_MODEL
from .models import ApprovalWorkflow, ApprovalInstance, ApprovalLog
from MultiScheme.models import Tenant

logger = logging.getLogger(__name__)

class ApprovalWorkflowEngine:
    def __init__(self,tenant: 'Tenant', target_object, action_type: str):
        self.tenant = tenant
        self.target = target_object
        self.action_type = action_type


    def start_workflow(self):
        workflow = ApprovalWorkflow.objects.filter(
            tenant=self.tenant,
            action_type=self.action_type,
            is_active=True
        ).first()

        if not workflow:
            raise ValueError(f"No active workflow found for action {self.action_type} for this tenant")

        instance = ApprovalInstance.objects.create(
            tenant=self.tenant,
            workflow=workflow,
            action_type=self.action_type,
            target_object_type=self.target.__class__.__name__,
            target_object_id=self.target.id,
            current_step=workflow.steps.first(),
            status='PENDING'
        )

        return instance


    def approve(self, user: 'AUTH_USER_MODEL', instance_id: int, comment: str = "", **kwargs):
        with transaction.atomic():
            instance = ApprovalInstance.objects.select_related(
                "current_step",
                "workflow"
            ).get(id=instance_id)
            step = instance.current_step

            # validate user
            self._validate_user_role(user, step)
            # check for duplicate actions for a user
            self._check_duplicate_action(user, instance, step)

            ApprovalLog.objects.create(
                instance=instance,
                step=step,
                user=user,
                action='APPROVED',
                comment=comment
            )

            kwargs.update({'comment':comment, 'user':user})
            # Proceed to finalize action if necessary
            self._advance_step(user,instance, step, kwargs=kwargs)


    def reject(self, user: 'AUTH_USER_MODEL', instance_id: int, comment: str = "", **kwargs):
        with transaction.atomic():
            instance = ApprovalInstance.objects.select_related(
                "current_step",
                "workflow"
            ).get(id=instance_id)
            step = instance.current_step

            # Validate user and check for duplicates
            self._validate_user_role(user, step)
            self._check_duplicate_action(user, instance, step)

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
            self._finalize(instance, approved=False, kwargs=kwargs)

    # HELPER METHODS
    def _validate_user_role(self, user, step):
        if not user.groups.filter(name=step.role).exists():
            raise PermissionError(f"User {user.username} does not have the required role {step.role} to approve this action")

    def _check_duplicate_action(self, user, instance, step):
        if ApprovalLog.objects.filter(
            instance=instance,
            step=step,
            user=user
        ).exists():
            raise ValueError(f"User {user.username} has already taken action in step {step.order} of workflow {instance.workflow.name}")

    def _advance_step(self,user, instance, step, **kwargs):
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
            else:
                instance.status = 'APPROVED'
                instance.finalized_at = timezone.now()
                self._finalize(instance, approved=True,kwargs=kwargs)

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