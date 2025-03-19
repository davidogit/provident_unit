from datetime import timedelta
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from .models import Member
from django.contrib.auth import get_user_model
from django.core.mail import send_mail,send_mass_mail
from ProvidentFund.settings import EMAIL_HOST_USER
from smtplib import SMTPException
from django.db import transaction
from twilio.rest import Client
import phonenumbers
from phonenumbers import parse as parse_phone, format_number, PhoneNumberFormat
import logging
from MultiScheme.models import TenantEventNotification
from django.core.mail import send_mail
from .models import WithdrawalRequest

logger = logging.getLogger(__name__)



# Task to check box for inactive users
@shared_task(bind=True)
def check_active_status_for_user(self):
    
    # loop throug each member and set the checkbox if required
    cut_off_date = timezone.now() - timedelta(14) #this will subtract 90 days from current date and returns a DateTime value
    # filters members who are not yet scheme-approved and were registered more than 90 days ago.
    members_to_update = Member.objects.filter(scheme_approval=False, registration_date__lte=cut_off_date)

    # Get user id from members
    users_ids = [member.user.id for member in members_to_update]
    # Fetch users
    User = get_user_model()

    # Fetch matching users using id
    users_to_update = User.objects.filter(id__in=users_ids)

    # looping users and changing status accordingly
    for user in users_to_update:
        user.inactive_status = True
        user.save()




# Task to delete Inactive users
@shared_task(bind=True)
@transaction.atomic #ensures that when there is an error in sending a mail to one person the process does not update any information for other users
def delete_inactive_users(self):

    try:
        # Filter inactive members based on their status
        inactive_users= get_user_model().objects.filter(inactive_status=True)

        # For every member who is about to be deleted a message is sent to notify them on the deletion of their account
        message_list = []
        for user in inactive_users:
            try:
                message=(
                        'PF Account Deletion Notification',
                        'Your account has been deleted due to you not being able to apply to a scheme after a given number of days. We hope to see you again when you qualify for a scheme.',
                        EMAIL_HOST_USER,
                        user.email,
                )
            except SMTPException as e:
                logger.error(f'An unexpected error occured when trying to send an email to {user.email} error: {e}')
            message_list.append(message)

        try:
            # send mass mail to users
            send_mass_mail(
                tuple(message_list),
                fail_silently=False
            )
            logger.info('Inactive members deleted successfully.')
            # Delete members
            inactive_users.delete()
        except Exception as e:
            logger.error('An error occured while deleting inactive users.')

    except Exception as e:
        logger.error(f'Transaction aborted : {e}')
        raise # the raise is used in this case to ensure that the error is masde known and all changes are rolled back


# Task to send OTP to members upon login
@shared_task(bind=True)
def send_otp_code(self,email,host,otp):
    # Send OTP to user via email
    send_mail(
        subject='PF CODE',
        message=f'Your OTP code is {otp}',
        from_email=EMAIL_HOST_USER,
        recipient_list=[email],
        fail_silently=False,
    )


@shared_task(bind=True)
def gen_send_email(self,recepient,message,subject):
    logger.info(f'Sending mails to: {recepient}')
    from_email=EMAIL_HOST_USER
    message_list = []
    for mail in recepient:
        message = (
            subject,
            message,
            from_email,
            [mail]
        )
        message_list.append(message)
    try:
        send_mass_mail(
            tuple(message_list),
            fail_silently=False
        )
    except SMTPException as smtp:
        logger.error(f'An SMTP error occured: {str(smtp)}')
    except Exception as e:
        logger.error(f'An error occured while trying to send mass mail: {str(e)}')





@shared_task
def notify_user_email_sms(tenant_id, member_name, first_name, last_name, user_email, tel_number, amount, scheme_name):
    """ Sends an email and SMS notification to the user and designated approvers for a withdrawal request """
    try:
        # Fetch recipients for `withdrawal_request` event
        recipients = TenantEventNotification.objects.filter(
            tenant_id=tenant_id,
            event="withdrawal_request"
        ).values_list('staff__email', flat=True)  # Get list of email addresses

        # Ensure there are recipients
        if not recipients:
            logger.warning("No recipients assigned for withdrawal_request event.")
            return "No recipients found."

        # Prepare email content
        subject = "PF | Withdrawal Request Submitted"
        message = (
            f"Dear {first_name} {last_name},\n\n"
            f"Your withdrawal request of ₵{amount:.2f} from the {scheme_name} scheme has been submitted successfully.\n\n"
            f"Status: Pending Approval\n"
            f"Your request is being processed and may take 2-3 business days to complete.\n\n"
            f"Best regards,\n"
            f"Provident Fund Team"
        )

        # Send email to user + assigned recipients
        send_mail(
            subject,
            message,
            from_email=settings.EMAIL_HOST_USER,  # Use the system email
            recipient_list=[user_email] + list(recipients),  # Send to user + approvers
            fail_silently=False,
        )

        logger.info(f"Email notification sent to user {user_email} and recipients: {', '.join(recipients)}")

        # Send SMS Notification (if phone number is valid)
        # if tel_number:
        #     parsed_phone = parse_phone(tel_number, "GH")
        #     if not phonenumbers.is_valid_number(parsed_phone):
        #         raise ValueError(f"Invalid phone number: {tel_number}")

        #     formatted_phone = format_number(parsed_phone, PhoneNumberFormat.E164)

        #     account_sid = 'ACe6e705f0732d1a51651131aa2516ab10'
        #     auth_token = 'eb8dec355cd270700f0b00e341d3dc46'
        #     client = Client(account_sid, auth_token)

        #     sms_message = (
        #         f"Hello {member_name}, your withdrawal request of ₵{amount:.2f} from the {scheme_name} scheme "
        #         f"has been received. It is pending approval and may take 2-3 business days."
        #     )

        #     client.messages.create(
        #         body=sms_message,
        #         from_='+14068004910',  # Replace with your Twilio phone number
        #         to=formatted_phone,
        #     )

        #     logger.info(f"SMS notification sent to {formatted_phone}")

        return f"Notification sent to user {user_email} and approvers."

    except Exception as e:
        logger.error(f"Error sending email/SMS: {str(e)}")
        return f"Error: {str(e)}"


@shared_task
def notify_withdrawal_approval(tenant_id, withdrawal_id):
    """Sends email notifications to the assigned approvers for a withdrawal request."""
    try:
        withdrawal = WithdrawalRequest.objects.get(id=withdrawal_id)
        tenant = withdrawal.tenant

        # Get approvers for withdrawal request
        recipients = TenantEventNotification.objects.filter(
            tenant=tenant,
            event="withdrawal_request"
        ).values_list('staff__email', flat=True)  # Get list of emails

        if not recipients:
            return "No recipients assigned for this event."
        logger.info(f"Sending approval email to: {', '.join(recipients)}")
        # Prepare email content
        subject = "Withdrawal Request Needs Approval"
        message = (
            f"Dear Approver,\n\n"
            f"A withdrawal request has been submitted for approval:\n\n"
            f"Staff ID: {withdrawal.staff.staff_number}\n"
            f"Scheme: {withdrawal.scheme.name}\n"
            f"Amount: ₵{withdrawal.amount:.2f}\n\n"
            f"Please review and approve the request."
        )

        # Send email
        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,  
            list(recipients),  
            fail_silently=False
        )

        logger.info(f" Email successfully sent to: {', '.join(recipients)}")
        return f" Email successfully sent to: {', '.join(recipients)}"

    except WithdrawalRequest.DoesNotExist:
        return "Withdrawal request not found."
    except Exception as e:
        return f"Error sending notification: {str(e)}"
