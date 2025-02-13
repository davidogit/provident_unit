from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from .models import Member
from django.contrib.auth import get_user_model
from django.core.mail import send_mail,send_mass_mail
from ProvidentFund.settings import EMAIL_HOST_USER
from smtplib import SMTPException
from django.db import transaction

import logging

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