from decimal import Decimal
from celery import shared_task
from django.http import JsonResponse
from .models import InvestmentDetail,BankInterest,DelayedInterest
from django.utils import timezone
from MultiScheme.models import Tenant, InvestmentScheme
# import contribution details from Contributions App
from contributions.models import StaffAPI,Contribution
from django.db import transaction
from django.db.models import Sum,FloatField,Q
import logging
from django.core.mail import send_mail
from ProvidentFund.settings import EMAIL_HOST_USER
from smtplib import SMTPException
from Member.models import SchemeApproval

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def member_interest(self):
    try:
        tenants = Tenant.objects.prefetch_related('investment_schemes__investments','staff_api') #prefetch schemes and staffs
        logger.info(f'Starting profit calculation for {tenants.count()} tenants.')

        for tenant in tenants:
            schemes = tenant.investment_schemes.all() #get associated schemes to tenant

            for scheme in schemes:
                # Get member allocation percentage
                member_allocation_percentage = scheme.distribution_percentage

                # Use reverse relationship b/n staff and contribution to calculate each members contribution
                members = tenant.staff_api.filter(
                    # tenant=tenant,
                    investment_scheme=scheme,
                    exited_flag=False
                ).annotate(total_contribution=Sum('contribution__total_contribution',filter=Q(contribution__approved_contribution=True,contribution__investment_scheme=scheme), output_field=FloatField()))

                #get investments associated with each scheme
                active_investments = scheme.investments.filter(
                    # investment_scheme=scheme,
                    # investment_scheme__tenant = tenant,
                    _remaining_days__gt=0,
                    _status='Active',
                    approval_status=False,
                    termination_status = False
                )

                delayed_interests = DelayedInterest.objects.filter(
                    investment_scheme=scheme,
                    _status='Not used'
                )

                bank_interests = BankInterest.objects.filter(
                    investment_scheme=scheme,
                    _status='Not used'
                )
                                
                # Aggregate total approved contributions for the scheme and tenant
                #prefetch staff_api in same query
                total_contribution = Contribution.objects.filter(investment_scheme__tenant=tenant,investment_scheme=scheme,approved_contribution=True).aggregate(total=Sum('total_contribution'))['total'] or 0.0

                # logger.info(f'TOTAL CONT {scheme.name} = {total_contribution}')


                # with transaction.atomic():
                # # Distribute Delayed Interests
                # for d_int in delayed_interests:
                #     try:
                #         if total_contribution > 0:
                #             for member in members:
                                
                #                 # get staff's actual amount
                #                 contribution = member.total_contribution or 0.0
                                
                #                 # Find date at which user joined the scheme
                #                 try:
                #                     scheme_subscription = SchemeApproval.objects.get(
                #                         staff=member, scheme=scheme, tenant=tenant, 
                #                         approved_by_hr=True)
                #                     subscription_date = scheme_subscription.approval_date
                #                 except SchemeApproval.DoesNotExist:
                #                     subscription_date = None

                #                 if subscription_date is not None and subscription_date.date() < d_int.created_date:
                #                     member.estimated_profit += (contribution / total_contribution) * (d_int.principal + d_int.interest)
                #                 else:
                #                     member.estimated_profit += 0.0
                #                 member.save()
                #             d_int.status = 'Used'
                #             d_int.save()
                #     except Exception as e:
                #         logger.error(f'Error occured{e}')

                # Distribute Bank Interests
                for b_int in bank_interests:
                    try:
                        if total_contribution > 0:
                            for member in members:
                                # collect member amount
                                contribution = member.total_contribution or 0.0

                                # check date user joined the scheme
                                try:
                                    scheme_subscription = SchemeApproval.objects.get(
                                        staff=member, scheme=scheme, tenant=tenant, 
                                        approved_by_hr=True)
                                    subscription_date = scheme_subscription.approval_date
                                except SchemeApproval.DoesNotExist:
                                    subscription_date = None

                                if subscription_date is not None and subscription_date.date() < b_int.created_date:
                                    member.estimated_profit += (contribution / total_contribution) * b_int.amount
                                else:
                                    member.estimated_profit += 0.0
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
                                # get member contribution
                                contribution = member.total_contribution or 0.0

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
                                    member.estimated_profit += profit

                                    # logger.info(f'Test to see member contribution: {contribution} for {member.first_name} profit:{profit} daily:{inv_daily_interest}')
                                else:
                                    member.estimated_profit += 0.0
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
    # Use reverse relationship b/n staff and contribution to calculate each members contribution relating to the scheme
    members = StaffAPI.objects.filter(
        tenant=tenant,
        investment_scheme=scheme,
        exited_flag=False
    ).annotate(total_contribution=Sum('contribution__total_contribution',filter=Q(contribution__approved_contribution=True,contribution__investment_scheme=scheme), output_field=FloatField()))

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
    
    # Get total contributions made to the scheme
    # Aggregate total approved contributions for the scheme and tenant
    total_contribution = Contribution.objects.filter(investment_scheme__tenant=tenant,investment_scheme=scheme,approved_contribution=True).aggregate(total=Sum('total_contribution'))['total'] or 0.0

    logger.info(f'Total: {total_contribution}')

    logger.info('STEP Try')
    try:
        logger.info('STEP 0')
        if total_contribution>0:
            logger.info('STEP 1')
            for member in members:
                
                # Get member actual amount
                contribution = member.total_contribution or 0.0

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
                    member.estimated_profit = (0-interest_on_inv)
                    member.save()
                else:
                    logger.info('Not working')
                    member.actual_amount += 0.0
        else:
            logger.info(f'No contribution found for {tenant.name} during actual interest calculation on {timezone.now}')
                    
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
            inv.remaining_days = (inv.interest_end_date-current_date).days
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

        # Check if today is inv maturity_date if True peform debit and credit for interest earned
        if current_date == inv.interest_end_date:
            from Chart_of_Accounts.models import AccountMapping
            scheme = inv.investment_scheme
            tenant = scheme.tenant
            # fetch related mapping
            try:
                mapping = AccountMapping.objects.get(tenant=tenant,scheme=scheme)
            except Exception as e:
                mapping = None
                logger.info(f'No mapping of "Interest Earned" for {tenant.name} - {scheme.name}')
            # Fetch debit and credit accounts

            debit_account = mapping.debit_acc
            credit_account = mapping.credit_acc

            if not debit_account or not credit_account:
                logger.info(f'Tenant: {tenant.name} Scheme: {scheme.name} missing debit or credit accounts')
                continue
            
            if debit_account.current_balance < inv.interest_amount:
                logger.info(f'Tenant: {tenant.name} Scheme: {scheme.name} Insufficient amount in {debit_account} account')
                continue

            try:
                with transaction.atomic():
                    # perform credit and debit
                    debit_account.current_balance -= inv.interest_amount
                    credit_account.current_balance += inv.interest_amount

                    # Save accounts 
                    debit_account.save()
                    credit_account.save()
                    logger.info(f'Interest transaction successful completed for: Tenant: {tenant.name} Scheme: {scheme.name}')
            except Exception as e:
                logger.info(f'Transaction failed for: Tenant: {tenant.name} Scheme: {scheme.name}')


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
    debit_or_credit = kwargs.get('debit_or_credit')
    debit_or_credit_amount = kwargs.get('debit_or_credit_amount')
    compounding_frequency = kwargs.get('compounding_frequency')
    duration = kwargs.get('duration')

    try:
        tenant = get_object_or_404(Tenant, id=tenant_id)
        scheme = InvestmentScheme.objects.filter(id=scheme_id,tenant=tenant).prefetch_related('account_mapping').first()
    
    except Tenant.DoesNotExist as e:
        logger.info(e)
    except InvestmentScheme.DoesNotExist as e:
        logger.info(e)

    logger.info(type(rollover_rate))
    logger.info(type(rollover_principal))
    
    try:
        with transaction.atomic():
            logger.info('Start')
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
                rollover_count = counter,
                compounding_frequency=compounding_frequency,
                years=duration,
            )
            logger.info('Start 1')
            # Debit and Credit operations
            if debit_or_credit:
                mapping = scheme.account_mapping.get(name='Roll Over')

                # Fetch debit and credit accounts from mapping obj
                debit_account = mapping.debit_acc
                credit_account = mapping.credit_acc
                logger.info('Start debit and credit operations')
                # perform debit anf credit operations
                debit_account.current_balance -= Decimal(debit_or_credit_amount)
                credit_account.current_balance += Decimal(debit_or_credit_amount)
                logger.info('Done with debit and credit operations')

                # save account balances
                debit_account.save()
                credit_account.save()
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


    # Annotate month's contribution to staff queryset
    staff_api = StaffAPI.objects.filter(tenant=tenant, investment_scheme__id=scheme_id).annotate(month_contribution=Sum('contribution__total_contribution',filter=Q(
        contribution__investment_scheme__tenant =tenant,
        contribution__investment_scheme__id=scheme_id,
        contribution__month=month,
        contribution__year=year,
        contribution__approved_contribution=True
    )))

    # List of staff updates
    staff_updates =[]

    for staff in staff_api:
        staff_contribution = staff.month_contribution

        if staff_contribution:
            staff.actual_amount += float(staff_contribution) 
            # if staff_contribution else 0.0
            print(f'Staff CONT= {staff_contribution}')
            # append to update list
            staff_updates.append(staff)

    # Using bulk update to effect all changes at once
    if staff_updates:
        StaffAPI.objects.bulk_update(staff_updates,['actual_amount'])
        logger.info(f'Updated {len(staff_updates)} staffs')
    else:
        logger.infor('No staff contributions to update')


# Task to calculate daily penalty on delayed interest object
# @shared_task(bind=True)
# def delayed_interest_penalty(self):
#     # get tenants using prefetch related
#     tenants = Tenant.objects.prefetch_related('investment_schemes__delayed_interest')

#     import calendar
#     year = timezone.now().year
#     is_leap = calendar.isleap(year)
#     days_in_year = 366 if is_leap else 365

#     for tenant in tenants:
#         # get schemes
#         schemes = tenant.investment_schemes.all()
#         if schemes.exists():
#             logger.info(f'Schemes: {schemes}')
#             for scheme in schemes:
#                 # Fetch DI objects
#                 delayed_interests = scheme.delayed_interest.filter(approved=False)
#                 logger.info(f'DI: {delayed_interests}')
#                 if delayed_interests.exists():
#                     for di in delayed_interests:
#                         # Extraxt params
#                         p = di.principal #principal of DI
#                         r = (di.rate_d_int)/100 #convert percentage to decimal
#                         n=days_in_year #compound rate=daily
#                         t= di.period_of_interest_calculation/days_in_year #period by which money is owed in years
#                         logger.info(f'Principal ={p}, Rate= {r}, T= {t}')
#                         # Compound Interest calculation
#                         c = p*(1+(r/n))**(n*t)
#                         logger.info(f'Compound I= {c}')
                        
#                         interest_per_day = (c - p)/n #interest
#                         logger.info(f'Interest Per day: {interest_per_day}')
#                         di.interest += interest_per_day
#                         di.save()

#                         logger.info(f'Tenant: {tenant.name} - Scheme: {scheme.name} - Daily Interest: {interest_per_day}')
#                 else:
#                     logger.info(f'No Delayed Interest for {tenant.name} {scheme.name}')
#         else:
#             logger.info(f'No schemes available for {tenant.name}')


