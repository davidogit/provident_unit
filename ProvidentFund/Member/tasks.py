from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from .models import Member
from Admin.models import User
from django.core.mail import send_mail
from ProvidentFund.settings import EMAIL_HOST_USER
from smtplib import SMTPException
from django.db import transaction

import logging

logger = logging.getLogger(__name__)


# Task to check box for inactive users
@shared_task(bind=True)
def check_active_status_for_user(self):
    
    # loop throug each member and set the checkbox if required
    cut_off_date = timezone.now() - timedelta(90) #this will subtract 90 days from current date and returns a DateTime value
    # filters members who are not yet scheme-approved and were registered more than 90 days ago.
    members_to_update = Member.objects.filter(scheme_approval=False, registration_date__lte=cut_off_date)

    # Update the active_status of members who are to be deleted
    members_to_update.update(user__inactive_status=True)



# Task to delete Inactive users
@shared_task(bind=True)
@transaction.atomic #ensures that when there is an error in sending a mail to one person the process does not update any information for other users
def delete_inactive_users(self):

    try:
        # Filter inactive members based on their status
        inactive_users= User.objects.filter(inactive_status=True)

        # For every member who is about to be deleted a message is sent to notify them on the deletion of their account
        for user in inactive_users:
            try:
                send_mail(
                        subject='PF Account Deletion Notification',
                        message='Your account has been deleted due to you not being able to apply to a scheme after a given number of days. We hope to see you again when you qualify for a scheme.',
                        from_email=EMAIL_HOST_USER,
                        recipient_list=[user.email],
                        fail_silently=False,
                )
            except SMTPException as e:
                logger.error(f'An unexpected error occured when trying to send an email to {user.email} error: {e}')

        # Delete members
        inactive_users.delete()

    except Exception as e:
        logger.error(f'Transaction aborted : {e}')
        raise # the raise is used in this case to ensure that the error is masde known and all changes are rolled back