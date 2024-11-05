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

                # total_contributions = members.aggregate(total=Sum(F('_amount')))['total'] or 0.0
                # logger.info(f'Tenant: {tenant.id}, Scheme: {scheme.id}, Total Contribution: {total_contributions}')

                active_investments = InvestmentDetail.objects.filter(
                    investment_scheme=scheme,
                    investment_scheme__tenant = tenant,
                    _remaining_days__gt=0,
                    _status='Active',
                    approval_status=False
                )

                delayed_interests = DelayedInterest.objects.filter(
                    investment_scheme=scheme,
                    _status='Not used'
                )

                bank_interests = BankInterest.objects.filter(
                    investment_scheme=scheme,
                    _status='Not used'
                )

                # Get total contributions of each scheme
                total_contribution = Contribution.objects.filter(investment_scheme=scheme, investment_scheme__tenant=tenant).aggregate(total=Sum(F('employee_amount')+F('employer_amount')+F('retro_employee_amount')+F('retro_employer_amount')))['total'] or 0.0


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

                                if subscription_date is not None and subscription_date.date() < inv.interest_start_date and inv._remaining_days > 0:
                                    profit = (contribution / total_contribution) * inv_daily_interest
                                    member.profit += profit
                                    logger.info(f'Test to see member contribution: {contribution} for {member.first_name} profit:{profit} daily:{inv_daily_interest}')
                                else:
                                    member.profit += 0.0
                                member.save()
                    except Exception as e:
                        logger.error(f'Error :{e}')                    

        logger.info(f'Profit successfully calculated for {timezone.now().date()}')
        return f'Profit successfully calculated for {timezone.now().date()}'
    
    except Exception as e:
        logger.error(f'Error in member_interest task: {str(e)}', exc_info=True)



# Task to calculate actual profit
@shared_task(bind=True)
def actual_member_interest(self,tenant_id,scheme_id,investment_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)
    scheme = get_object_or_404(InvestmentScheme, id=scheme_id)
    members = StaffAPI.objects.filter(
                    tenant=tenant,
                    investment_scheme=scheme,
                    exited_flag=False
                )

    inv = InvestmentDetail.objects.get(
                    id=investment_id,
                    investment_scheme=scheme,
                    investment_scheme__tenant = tenant,
                    approval_status=True
                )
    
    total_contribution = Contribution.objects.filter(investment_scheme=scheme, investment_scheme__tenant=tenant).aggregate(total=Sum(F('employee_amount')+F('employer_amount')+F('retro_employee_amount')+F('retro_employer_amount')))['total']

    logger.info(f'Total: {total_contribution}')

    try:
        if total_contribution>0:
            for member in members:

                contribution = Contribution.objects.filter(member=member,investment_scheme=scheme, investment_scheme__tenant=tenant).aggregate(total=Sum(F('employee_amount')+F('employer_amount')+F('retro_employee_amount')+F('retro_employer_amount')))['total']

                
                
                try:
                    scheme_subscription = SchemeApproval.objects.get(
                            staff=member, scheme=scheme, tenant=tenant, 
                            approved_by_hr=True)
                    subscription_date = scheme_subscription.approval_date
                except SchemeApproval.DoesNotExist:
                    subscription_date = None

                # Check if user was approved before an investment was made
                if subscription_date is not None and subscription_date.date() < inv.interest_start_date:
                    member.actual_profit += (contribution / total_contribution) * inv.interest_amount
                else:
                    member.actual_profit += 0.0
                member.save()
            
        logger.info(f'Actual profit calculated for: {tenant.name}\'s members at: {timezone.now()}')

    except Exception as e:
        logger.error(f'Error: {e}')

        # If there is any error uncheck investment to make sure the error does not affect the investment status
        inv.approval_status = False
        inv.save()
        logger.info('Changes were not saved due to an error')
        ##########






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


# Task to handle client page visit
from .models import AuditTrail
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
@shared_task(bind=True)
def track_page_visits(self,user_id,path,view_name,user_ip,*args):
    
    try:
        # print(user_id)
        user = get_object_or_404(get_user_model(), pk=int(user_id))
    except (ValueError,TypeError) as e:
        logger(f'Error {e}')

    AuditTrail.objects.create(
        user = user,
        model_name = 'Page Visited',
        action = 'visited',
        object_id = user.pk,
        changes = f'{user.username} visited:{view_name}  URL:{path} at:  {timezone.now()} IP:  {user_ip}',
        timestamp = timezone.now()
    )