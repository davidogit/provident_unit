from celery import shared_task
from .models import InvestmentDetail,BankInterest,DelayedInterest
from django.utils import timezone
from MultiScheme.models import Tenant, InvestmentScheme
# import contribution details from Contributions App
from contributions.models import StaffAPI,Contribution
from django.db import transaction
from django.db.models import Sum,F
import logging
from django.core.mail import send_mail
from ProvidentFund.settings import EMAIL_HOST_USER
from smtplib import SMTPException
from Member.models import SchemeApproval

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def member_interest(self):
    try:
        tenants = Tenant.objects.all()
        logger.info(f'Starting profit calculation for {tenants.count()} tenants.')

        for tenant in tenants:
            schemes = InvestmentScheme.objects.filter(tenant=tenant)

            for scheme in schemes:
                members = StaffAPI.objects.filter(
                    tenant=tenant,
                    investment_scheme=scheme,
                    exited_flag=False
                )

                total_contribution = members.aggregate(total=Sum(F('_amount')))['total'] or 0.0
                logger.info(f'Tenant: {tenant.id}, Scheme: {scheme.id}, Total Contribution: {total_contribution}')

                active_investments = InvestmentDetail.objects.filter(
                    investment_scheme=scheme,
                    investment_scheme__tenant = tenant,
                    _remaining_days__gt=0,
                    _status='Active',
                    approval_status=False
                )

                approved_investments = InvestmentDetail.objects.filter(
                    investment_scheme=scheme,
                    investment_scheme__tenant = tenant,
                    approval_status=True
                )

                delayed_interests = DelayedInterest.objects.filter(
                    investment_scheme=scheme,
                    _status='Not used'
                )

                bank_interests = BankInterest.objects.filter(
                    investment_scheme=scheme,
                    _status='Not used'
                )



                # with transaction.atomic():
                # Distribute Delayed Interests
                for d_int in delayed_interests:
                    try:
                        if total_contribution > 0:
                            for member in members:
                                contribution = Contribution.objects.filter(member=member,investment_scheme=scheme, investment_scheme__tenant=tenant).aggregate(total=Sum(F('employee_amount')+F('employer_amount')+F('retro_employee_amount')+F('retro_employer_amount')))['total'] or 0

                               
                                
                                try:
                                    scheme_subscription = SchemeApproval.objects.get(
                                        staff=member, scheme=scheme, tenant=tenant, 
                                        approved_by_hr=True)
                                    subscription_date = scheme_subscription.approval_date
                                except SchemeApproval.DoesNotExist:
                                    subscription_date = None

                                if subscription_date is not None and subscription_date.date() < d_int.created_date:
                                    member.profit += (contribution / total_contribution) * d_int.amount
                                else:
                                    member.profit += 0.0
                                member.save()
                        d_int.status = 'Used'
                        d_int.save()
                    except Exception as e:
                        logger.error(f'Error occured{e}')

                # Distribute Bank Interests
                for b_int in bank_interests:
                    try:
                        if total_contribution > 0:
                            for member in members:

                                contribution = Contribution.objects.filter(member=member,investment_scheme=scheme, investment_scheme__tenant=tenant).aggregate(total=Sum(F('employee_amount')+F('employer_amount')+F('retro_employee_amount')+F('retro_employer_amount')))['total']

                                try:
                                    scheme_subscription = SchemeApproval.objects.get(
                                        staff=member, scheme=scheme, tenant=tenant, 
                                        approved_by_hr=True)
                                    subscription_date = scheme_subscription.approval_date
                                except SchemeApproval.DoesNotExist:
                                    subscription_date = None

                                if subscription_date is not None and subscription_date.date() < b_int.created_date:
                                    member.profit += (contribution / total_contribution) * b_int.amount
                                else:
                                    member.profit += 0.0
                                member.save()
                        b_int.status = 'Used'
                        b_int.save()
                    except Exception as e:
                        logger.error(f'Error {e}')

                # Estimated Revenue Distribution
                for inv in active_investments:
                    try:
                        if inv.tenure > 0:
                            inv_daily_interest = inv.interest_amount / inv.tenure
                        else:
                            inv_daily_interest = 0.0

                        for member in members:
                            contribution = Contribution.objects.filter(member=member,investment_scheme=scheme, investment_scheme__tenant=tenant).aggregate(total=Sum(F('employee_amount')+F('employer_amount')+F('retro_employee_amount')+F('retro_employer_amount')))['total']


                            try:
                                scheme_subscription = SchemeApproval.objects.get(
                                        staff=member, scheme=scheme, tenant=tenant, 
                                        approved_by_hr=True)
                                subscription_date = scheme_subscription.approval_date
                            except SchemeApproval.DoesNotExist:
                                subscription_date = None                            

                            if subscription_date is not None and subscription_date.date() < inv.interest_start_date and inv._remaining_days > 0:
                                profit = (contribution / inv.principal_amount) * inv_daily_interest
                                member.profit += profit
                                logger.info(f'Test to see member contribution: {contribution} for {member.first_name} profit:{profit} daily:{inv_daily_interest}')
                            else:
                                member.profit += 0.0
                            member.save()
                    except Exception as e:
                        logger.error(f'Error :{e}')



                # Actual Revenue Distribution
                for inv in approved_investments:
                    try:
                        for member in members:

                            contribution = Contribution.objects.filter(member=member,investment_scheme=scheme, investment_scheme__tenant=tenant).aggregate(total=Sum(F('employee_amount')+F('employer_amount')+F('retro_employee_amount')+F('retro_employer_amount')))['total']

                            try:
                                scheme_subscription = SchemeApproval.objects.get(
                                        staff=member, scheme=scheme, tenant=tenant, 
                                        approved_by_hr=True)
                                subscription_date = scheme_subscription.approval_date
                            except SchemeApproval.DoesNotExist:
                                subscription_date = None

                            logger.info(f'sub_date:{subscription_date.date()} and inv_date:{inv.interest_start_date}')
                            if subscription_date is not None and subscription_date.date() < inv.interest_start_date:
                                member.actual_profit += (contribution / inv.principal_amount) * inv.interest_amount
                            else:
                                member.profit += 0.0
                            member.save()
                    except Exception as e:
                        logger.error(f'Error: {e}')                    

        logger.info(f'Profit successfully calculated for {timezone.now().date()}')
        return f'Profit successfully calculated for {timezone.now().date()}'
    
    except Exception as e:
        logger.error(f'Error in member_interest task: {str(e)}', exc_info=True)
    


# Task to reduce remaining days by 1 every midnight 12:00 am
@shared_task(bind=True)
def reduce_date(self):
    # Filter only unapproved investments
    investments = InvestmentDetail.objects.filter(approval_status=False)
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

        ###########################################################################
        # Send Email to tenant
        try:
            if inv.remaining_days == 0:

                # send email notification to tenant email
                tenant_email = inv.investment_scheme.tenant.email

                send_mail(
                    subject='Investment Due',
                    message= f'Investment with ID:{inv.id} and Acc No.: {inv.account_number} is due',
                    from_email=EMAIL_HOST_USER,
                    recipient_list=[tenant_email,],
                    fail_silently=False
                )

        # Handling any error that might occur from sending the notification
        except SMTPException as e:
            logger.error(f'Unexpected error occured when trying to send due notification to tenant:{inv.investment_scheme.tenant.name} error:{e}')
    

        ###########################################################################

    # Using bulk update to save every instance at once for efficiency
    # InvestmentDetail.objects.bulk_update(updates, ['_remaining_days','_status'])
    try:
        with transaction.atomic():
            InvestmentDetail.objects.bulk_update(updates, ['_remaining_days','_status'])
            logger.info('Investment Details Updated Succesfully')
    except Exception as e:
        logger.error(f'Error trying to update Investment Details {e}')

    return 'day_reduced_by_1'













    # for member in members:
    #     # Get member total contributions for a specific scheme
    #     contribution = Contribution.objects.filter(member=member,investment_scheme=scheme, investment_scheme__tenant=tenant).aggregate(total=Sum('total_contributions'))['total']

    #     # checks
    #     print(f'{member.first_name}\'s total contribution for {scheme.name}: {contribution}')

    #     # Ensure member profit is not none before calculation
    #     if contribution is None:
    #         contribution = 0.0




# # Task to calculate profit for members daily
# @shared_task(bind=True)
# def member_interest(self):
#     # Loop through tenants
#     tenants = Tenant.objects.all()

#     logger.info(f'Processing {tenants.count()} Tenants.')
#     for tenant in tenants:

#         # Fetch schemes
#         schemes = InvestmentScheme.objects.filter(tenant=tenant)

#         # loop through all schemes relating to a tenant
#         for scheme in schemes:
#             # Get all active members
#             members = StaffAPI.objects.filter(tenant=tenant,investment_scheme=scheme, exited_flag = False)

#             # Sum up every members contribution into one single value as total_contribution based on tenant and scheme
#             total_contribution = StaffAPI.objects.filter(tenant=tenant,investment_scheme=scheme, exited_flag = False).aggregate(total=Sum('_amount'))['total']

#             # Making sure total_contribution is not None
#             if total_contribution is None:
#                 total_contribution = 0.0

#             # print(f'Total contribution = {total_contribution}')

#             # Get investments with remaining_days >0 and status == 'Active' and unapproved for estimated revenue
#             active_investments = InvestmentDetail.objects.filter(investment_scheme__tenant=tenant,investment_scheme=scheme, _remaining_days__gt=0, _status = 'Active',approval_status=False)
#             print(active_investments)

#             # Get investments with remaining_days >0 and status == 'Active' and unapproved for estimated revenue
#             approved_investments = InvestmentDetail.objects.filter(investment_scheme__tenant=tenant,investment_scheme=scheme,approval_status=True)
#             print(approved_investments)

#             # Get delayed interest if theres any
#             delayed_interest = DelayedInterest.objects.filter(investment_scheme__tenant=tenant,investment_scheme=scheme,_status = 'Not used')

#             # Get bank interest if theres any
#             bank_interest = BankInterest.objects.filter(investment_scheme__tenant=tenant,investment_scheme=scheme,_status = 'Not used')
                
#             # Distribute Delayed Interest based on members contribution
#             for d_int in delayed_interest:
#                 # Update member profit
#                 for member in members:
#                     # Get member total contributions for a specific scheme
#                     contribution = Contribution.objects.filter(member=member,investment_scheme=scheme, investment_scheme__tenant=tenant).aggregate(total=Sum('total_contributions'))['total']
                    
#                     member.profit += ((contribution/total_contribution)*d_int.amount)
                
#                 # change the status of delayed interest after it has been used
#                 d_int.status = 'Used'
#                 # Save the new status for delayed interest
#                 d_int.save()

#             # Distribute Bank Interest based on members contribution
#             for b_int in bank_interest:
#                 # Update member profit
#                 for member in members:
#                     # Get member total contributions for a specific scheme
#                     contribution = Contribution.objects.filter(member=member,investment_scheme=scheme, investment_scheme__tenant=tenant).aggregate(total=Sum('total_contributions'))['total']

#                     member.profit += ((contribution/total_contribution)*b_int.amount)

#                 # change the status of Bank interest
#                 b_int.status = 'Used'
#                 # Save the new status of bank interest
#                 b_int.save()

#             # Calculation for estimated revenue distributed daily
#             for inv in active_investments:
#                 days_left = inv.remaining_days
#                 total_inv = inv.principal_amount
#                 inv_interest = inv.interest_amount
#                 tenure = inv.tenure

#                 # loop through members
#                 for member in members:

#                     # Get member total contributions for a specific scheme
#                     contribution = Contribution.objects.filter(member=member,investment_scheme=scheme, investment_scheme__tenant=tenant).aggregate(total=Sum('total_contributions'))['total']

#                     # Check if member is elidgible for profit based on the time he/she joined the PF
#                     if (member.subscription_date < inv.interest_start_date):

#                         # checks if tenure is not expired
#                         if days_left>0:
#                             inv_daily_interest = inv_interest/tenure
#                             member.profit += ((contribution/total_inv)*inv_daily_interest)
#                         else:
#                             inv_daily_interest = 0.0
#                             member.profit +=0.0
#                     # Else if member joined after a particular investment is bought he/she do not get any profit
#                     else:
#                         member.profit += 0.0
            
#             # Calculation for approved investments and actual revenue

#             for inv in active_investments:
#                 interest = inv.interest_amount
#                 principal = inv.principal_amount

#                 for member in members:
#                     # Get member total contributions for a specific scheme
#                     contribution = Contribution.objects.filter(member=member,investment_scheme=scheme, investment_scheme__tenant=tenant).aggregate(total=Sum('total_contributions'))['total']

#                     # Check if member is elidgible for profit based on the time he/she joined the PF
#                     if (member.subscription_date < inv.interest_start_date):
#                         member.profit += ((contribution/principal)*interest)
#                     else:
#                         member.profit += 0.0

#             member.save()

#     return f'Profit successfully calculated for {timezone.now().date()}'
