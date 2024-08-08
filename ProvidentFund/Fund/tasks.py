from celery import shared_task
from .models import InvestmentDetail,BankInterest,DelayedInterest
from django.utils import timezone

# import contribution details from Contributions App
from contributions.models import StaffAPI

from django.db import transaction
from django.db.models import Sum
import logging

logger = logging.getLogger(__name__)


# Task to calculate profit for members daily
@shared_task(bind=True)
def member_interest(self):
    # Get all active members
    members = StaffAPI.objects.filter(exited_flag = False)

    # Sum up every members contribution into one single value as total_contribution

    total_contribution = StaffAPI.objects.filter(exited_flag = False).aggregate(total=Sum('_amount'))['total']

    # Making sure total_contribution is not None
    if total_contribution is None:
        total_contribution = 0.0

    print(f'Total contribution = {total_contribution}')

    # Get investments with remaining_days >0 and status == 'Active'
    investments = InvestmentDetail.objects.filter(_remaining_days__gt=0, _status = 'Active')
    print(investments)

    # Get delayed interest if theres any
    delayed_interest = DelayedInterest.objects.filter(_status = 'Not used')

    # Get bank interest if theres any
    bank_interest = BankInterest.objects.filter(_status = 'Not used')

    for member in members:
        contribution = member.amount

        # Ensure member profit is not none before calculation
        if member.profit is None:
            member.profit = 0.0
        
        # Distribute Delayed Interest based on members contribution
        for d_int in delayed_interest:
            # Update member profit
            member.profit += ((contribution/total_contribution)*d_int.amount)
            
            # change the status of delayed interest after it has been used

            d_int.status = 'Used'

            # Save the new status for delayed interest
            d_int.save()

        # Distribute Bank Interest based on members contribution
        for b_int in bank_interest:
            # Update member profit
            member.profit += ((contribution/total_contribution)*b_int.amount)

            # change the status of Bank interest
            b_int.status = 'Used'

            # Save the new status of bank interest
            b_int.save()

        for inv in investments:
            days_left = inv.remaining_days
            total_inv = inv.principal_amount
            inv_interest = inv.interest_amount
            tenure = inv.tenure

            # Check if member is elidgible for profit based on the time he/she joined the PF
            if (member.subscription_date < inv.interest_start_date):

                # checks if tenure is not expired
                if days_left>0:
                    inv_daily_interest = inv_interest/tenure
                    member.profit += ((contribution/total_inv)*inv_daily_interest)
                else:
                    inv_daily_interest = 0.0
                    member.profit +=0.0
            # Else if member joined after a particular investment is bought he/she do not get any profit
            else:
                member.profit += 0.0      
        member.save()

    return f'Profit successfully calculated for {timezone.now().date()}'


# Task to reduce remaining days by 1 every midnight 12:00 am
@shared_task(bind=True)
def reduce_date(self):
    investments = InvestmentDetail.objects.all()
    current_date = timezone.now().date()

    # update[] will hold all potential updates and save them in bulk
    updates = []
    for inv in investments:
        # Checks if the investment is within duration
        if (inv.interest_start_date <= current_date <= inv.interest_end_date):     
            inv.remaining_days -=1
            inv.status = 'Active'
        
        # Checks if investment is expired
        elif (current_date>inv.interest_end_date):
            inv.remaining_days = 0
            inv.status = 'Expired'

        # checks if investment is yet to begin
        elif (current_date < inv.interest_start_date):
            remaining_days = inv.tenure
            inv.remaining_days = remaining_days
            inv.status = 'Not Start'

        # Make sures remaining days do not go to negative due to daily deduction
        if inv.remaining_days<0:
            inv.remaining_days = 0

        updates.append(inv)
    
    # Using bulk update to save every instance at once for efficiency
    # InvestmentDetail.objects.bulk_update(updates, ['_remaining_days','_status'])
    try:
        with transaction.atomic():
            InvestmentDetail.objects.bulk_update(updates, ['_remaining_days','_status'])
            logger.info('Investment Details Updated Succesfully')
    except Exception as e:
        logger.error(f'Error trying to update Investment Details {e}')

    return 'day_reduced_by_1'