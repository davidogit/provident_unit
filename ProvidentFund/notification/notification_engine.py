from smtplib import SMTPException

from django.contrib.auth.models import Group
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
import logging


from approval_workflow.models import ApprovalInstance

logger = logging.getLogger(__name__)


def send_approval_email_to_next_step_users(instance: 'ApprovalInstance'):
    group = Group.objects.get(name=instance.current_step.role)
    users = group.user_set.filter(is_active=True,tenant=instance.tenant).distinct()

    for user in users:
        context = {
            "subject": f"Approval Needed: {instance.workflow.name}",
            'email_title':'Approval Request',
            'email_subtitle':'You have been assigned to approve the following workflow step:',
            'user_name':user.get_full_name() or user.username,
            'message_content': f"""
            <p>You have been assigned to approve a step in the <strong>{instance.workflow.name}</strong> workflow.</p>
            <p><strong>Action Type:</strong> {instance.action_type.replace("_", " ").title()}</p>
            <p>Please click the button below to proceed to your approval page.</p>
            """,
            'cta_button_text':"Review Now",
            "cta_button_url": f"{settings.SITE_URL}/{instance.tenant.id}/fund/dashboard",

            "info_box_content": f"This action requires {instance.current_step.required_approvals} approval(s) from role: <strong>{instance.current_step.role}</strong>.",
            "alert_type": "info",
            "alert_message": f"This is step {instance.current_step.order} in the approval process.",
            "closing_message": "If you have any questions, please contact your scheme administrator.",
            "company_name": "PF Platform",
            "company_email": "support@pfplatform.com",
            "company_phone": "+233 (0) 123 456 789",
            "company_address": "Suite 202, Accra Digital Centre, Accra, Ghana",
        }
        subject = context['subject']
        from_email = settings.DEFAULT_FROM_EMAIL
        html_content = render_to_string("email_template.html", context)

        text_content = f"Hi {context['user_name']},\n\nYou have an approval request for '{instance.workflow.name}'. Please login to take action."
        try:
            msg = EmailMultiAlternatives(subject, text_content, from_email, [user.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
        except SMTPException as smtp_e:
            logger.error(f'Error sending email: {smtp_e}')
        except Exception as e:
            logger.error(f'Error sending email: {e}')
