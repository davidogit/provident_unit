from celery import shared_task
from django.http import JsonResponse
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
                # Get member allocation percentage
                member_allocation_percentage = scheme.distribution_percentage


                members = StaffAPI.objects.filter(
                    tenant=tenant,
                    investment_scheme=scheme,
                    exited_flag=False
                )

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
                # total_contribution = Contribution.objects.filter(investment_scheme=scheme, investment_scheme__tenant=tenant,approved_contribution=True).aggregate(total=Sum(F('employee_amount')+F('employer_amount')+F('retro_employee_amount')+F('retro_employer_amount')))['total'] or 0.0
                
                
                # Get all members of scheme and sump up their actual amount which will be used in distribution by proportion
                total_contribution = StaffAPI.objects.filter(
                    tenant=tenant,
                    investment_scheme = scheme,
                    exited_flag=True
                ).aggregate(total = Sum('actual_amount'))['total'] or 0.0

                # with transaction.atomic():
                # Distribute Delayed Interests
                for d_int in delayed_interests:
                    try:
                        if total_contribution > 0:
                            for member in members:
                                
                                # get staff's actual amount
                                contribution = member.actual_amount or 0.0
                                
                                # Find date at which user joined the scheme
                                try:
                                    scheme_subscription = SchemeApproval.objects.get(
                                        staff=member, scheme=scheme, tenant=tenant, 
                                        approved_by_hr=True)
                                    subscription_date = scheme_subscription.approval_date
                                except SchemeApproval.DoesNotExist:
                                    subscription_date = None

                                if subscription_date is not None and subscription_date.date() < d_int.created_date:
                                    member.actual_amount += (contribution / total_contribution) * d_int.amount
                                else:
                                    member.actual_amount += 0.0
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
                                # collect member amount
                                contribution = member.actual_amount or 0.0

                                # check date user joined the scheme
                                try:
                                    scheme_subscription = SchemeApproval.objects.get(
                                        staff=member, scheme=scheme, tenant=tenant, 
                                        approved_by_hr=True)
                                    subscription_date = scheme_subscription.approval_date
                                except SchemeApproval.DoesNotExist:
                                    subscription_date = None

                                if subscription_date is not None and subscription_date.date() < b_int.created_date:
                                    member.actual_amount += (contribution / total_contribution) * b_int.amount
                                else:
                                    member.actual_amount += 0.0
                                member.save()
                            b_int.status = 'Used'
                            b_int.save()
                    except Exception as e:
                        logger.error(f'Error {e}')

                # Estimated Revenue Distribution
                for inv in active_investments:
                    try:
                        if inv.tenure > 0:
                            # calculate member allocation equivalent
                            members_int_allocation = (inv.interest_amount*(member_allocation_percentage/100))

                            # calculate daily member allocation
                            inv_daily_interest = (members_int_allocation / inv.tenure)
                        else:
                            inv_daily_interest = 0.0

                        if total_contribution > 0:
                            for member in members:
                                # get member amount
                                contribution = member.actual_amount or 0.0

                                # Check date user joined scheme
                                try:
                                    scheme_subscription = SchemeApproval.objects.get(
                                            staff=member, scheme=scheme, tenant=tenant, 
                                            approved_by_hr=True)
                                    subscription_date = scheme_subscription.approval_date
                                except SchemeApproval.DoesNotExist:
                                    subscription_date = None                            

                                # Calculate Estimated income NB: Does not include Principal of member
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
    
    # Get member allocation percentage
    member_allocation_percentage=scheme.distribution_percentage

    # Calculate member allocation
    member_allocation = (inv.interest_amount*(member_allocation_percentage/100))
    
    # Get all members of scheme and sump up their actual amount which will be used in distribution by proportion
    total_contribution = StaffAPI.objects.filter(
        tenant=tenant,
        investment_scheme = scheme,
        exited_flag=False
    ).aggregate(total = Sum('actual_amount'))['total'] or 0.0

    logger.info(f'Total: {total_contribution}')

    logger.info('STEP Try')
    try:
        logger.info('STEP 0')
        if total_contribution>0:
            logger.info('STEP 1')
            for member in members:
                
                # Get member actual amount
                contribution = member.actual_amount or 0.0

                logger.info(f'User Contribution: {contribution}')

                logger.info('STEP 2')
                
                # Check date user joined scheme
                try:
                    scheme_subscription = SchemeApproval.objects.get(
                        staff=member,
                        scheme=scheme,
                        tenant=tenant, 
                        approved_by_hr=True)
                    logger.info(f'STEP 3: {scheme_subscription.approval_date}')
                    subscription_date = scheme_subscription.approval_date
                except SchemeApproval.DoesNotExist:
                    subscription_date = None
                
                logger.info('STEP 4')

                # Check if user was approved before an investment was made
                if subscription_date is not None and subscription_date.date() < inv.interest_start_date:
                    
                    interest_on_inv = (contribution / total_contribution) * member_allocation

                    # Add interest to member actual amount
                    member.actual_amount += interest_on_inv
                    
                    # Subtract interest from member estimated amount
                    member.profit = (0-interest_on_inv)
                    member.save()
                else:
                    logger.info('Not working')
                    member.actual_amount += 0.0
                
            
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
                    message= f'Investment with Invoice Number:{inv.invoice_number} and Acc No.: {inv.account_number} is due. Approve investment if funds have been recorgnised',
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
        timestamp = timezone.now(),
        name = user.username
    )


@shared_task(bind=True)
def rollover_inv_creation(self,**kwargs):
    tenant_id = kwargs.get('tenant_id')
    scheme_id = kwargs.get('scheme_id')
    inv_name = kwargs.get('inv_name')
    rollover_rate = kwargs.get('rollover_rate')
    rollover_principal = kwargs.get('rollover_principal')
    start_date = kwargs.get('start_date')
    maturity_date = kwargs.get('maturity_date')
    inv_type = kwargs.get('inv_type')
    account_type = kwargs.get('account_type')
    account_number = kwargs.get('account_number')
    counter = kwargs.get('counter')

    try:
        tenant = get_object_or_404(Tenant, id=tenant_id)
        scheme = get_object_or_404(InvestmentScheme,id=scheme_id,tenant=tenant)
    
    except Tenant.DoesNotExist as e:
        logger.info(e)
    except InvestmentScheme.DoesNotExist as e:
        logger.info(e)
    
    try:
        InvestmentDetail.objects.create(
            investment_scheme = scheme,
            account_name=inv_name,
            investment_type=inv_type,
            interest_percentage=rollover_rate,
            principal_amount=rollover_principal,
            interest_start_date=start_date,
            interest_end_date=maturity_date,
            account_number=account_number,
            account_type=account_type,
            rollover_count = counter
        )
        logger.info(f'Roll over for inv {inv_name} added')
    except Exception as e:
        logger.info(f'Inv Adding Error: {e}')


# Task to calculate and add contribution to user actual_amount when a contribution is approved
@shared_task(bind=True)
def calculate_staff_contribution(self,scheme_id,tenant_id,month,year):
    scheme_id = scheme_id
    tenant_id = tenant_id
    logger.info(f'Tenant ID: {tenant_id}')
    tenant = Tenant.objects.get(id=tenant_id)
    month = month
    year = year


    # Add contributions to member principal
    staff_api = StaffAPI.objects.filter(tenant=tenant, investment_scheme__id=scheme_id)

    # List of staff updates
    staff_updates =[]

    for staff in staff_api:
        staff_contribution = Contribution.objects.get(investment_scheme__tenant = tenant,investment_scheme__id=scheme_id,month=month,year=year, approved_contribution=True,member=staff).total_contributions
        

        if staff_contribution:
            staff.actual_amount += float(staff_contribution) 
            # if staff_contribution else 0.0

            # append to update list
            staff_updates.append(staff)

    # Using bulk update to effect all changes at once
    StaffAPI.objects.bulk_update(staff_updates,['actual_amount'])