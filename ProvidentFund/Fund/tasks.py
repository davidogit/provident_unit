from datetime import timedelta
import calendar
from decimal import Decimal
from celery import shared_task
from django.http import JsonResponse
from .models import InvestmentDetail,BankInterest,DelayedInterest
from django.utils import timezone
from MultiScheme.models import Tenant, InvestmentScheme,TenantEventNotification
from django.core.exceptions import ObjectDoesNotExist
# import contribution details from Contributions App
from contributions.models import StaffAPI,Contribution,Membership
from django.db import transaction
from django.db.models import Sum,FloatField,Q,DecimalField
import logging
from django.core.mail import send_mail,EmailMessage,send_mass_mail
from ProvidentFund.settings import EMAIL_HOST_USER
from smtplib import SMTPException
from Member.models import SchemeApproval
from openpyxl import Workbook
from Fund.models import ScheduledPaymentDates,BankSheet
from io import BytesIO
from django.core.files.base import ContentFile
logger = logging.getLogger(__name__)

@shared_task(bind=True)
def member_interest(self):
    try:
        tenants = Tenant.objects.prefetch_related('investment_schemes__investments','staff_api','membership') #prefetch schemes and staffs
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
                ).annotate(total_contribution=Sum('contribution__total_contribution',filter=Q(contribution__approved_contribution=True,contribution__investment_scheme=scheme), output_field=DecimalField()))

                # Get MEMBERSHIPS NB:This model is where the accumulation will be done on not the member(StaffAPI model)
                memberships = tenant.membership.all().filter(
                    scheme=scheme
                )


                #get investments associated with each scheme
                active_investments = scheme.investments.filter(
                    # investment_scheme=scheme,
                    # investment_scheme__tenant = tenant,
                    _remaining_days__gt=0,
                    _status='Active',
                    approval_status=False,
                    termination_status = False
                )
                logger.info(f'INVESTMENTS: {active_investments}')

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
                total_contribution = Contribution.objects.filter(investment_scheme__tenant=tenant,investment_scheme=scheme,approved_contribution=True).aggregate(total=Sum('total_contribution'))['total'] or Decimal(0.0)

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


                # Estimated Revenue Distribution
                for inv in active_investments:
                    try:
                        if inv.tenure > 0:
                            # calculate member allocation equivalent
                            members_int_allocation = (inv.interest_amount*(member_allocation_percentage/100))

                            # calculate daily member allocation
                            inv_daily_interest = (members_int_allocation / inv.tenure)
                        else:
                            inv_daily_interest = Decimal(0.0)

                        if total_contribution > 0:
                            for member in members:
                                # get member contribution
                                contribution = member.total_contribution or Decimal(0.0)
                                logger.info(f'TOTAL CONT {scheme.name} = {total_contribution}')
                                logger.info(f'MEMBER CONTRIBUTION {contribution}')
                                # get membership
                                try:
                                    membership = memberships.get(
                                        staff=member
                                    )
                                except Exception as e:
                                    membership = None
                                    logger.info(f'Membership for: {member.first_name} {member.last_name} not found')

                                if membership:
                                    # Check date user joined scheme
                                    try:
                                        scheme_subscription = SchemeApproval.objects.get(
                                                staff=member, scheme=scheme, tenant=tenant, 
                                                approved_by_hr=True)
                                        subscription_date = scheme_subscription.approval_date
                                    except SchemeApproval.DoesNotExist:
                                        subscription_date = None                            

                                    # Calculate Estimated income NB: Does not include Principal of member
                                    if subscription_date and subscription_date.date() < inv.interest_start_date and inv._remaining_days > 0:

                                        profit = (contribution / total_contribution) * inv_daily_interest
                                        membership.estimated_profit += Decimal(profit)

                                        # logger.info(f'Test to see member contribution: {contribution} for {member.first_name} profit:{profit} daily:{inv_daily_interest}')
                                        logger.info(f'DISTRIBUTION PERCENTAGE: {member_allocation_percentage}')
                                        logger.info(f'MEMBERSHIPS: {membership}')
                                    else:
                                        membership.estimated_profit += Decimal(0.0)
                                    membership.save()
                    except Exception as e:
                        logger.error(f'Error :{e}')                    

        logger.info(f'Profit successfully calculated for {timezone.now().date()}')
        return f'Profit successfully calculated for {timezone.now().date()}'
    
    except Exception as e:
        logger.error(f'Error in member_interest task: {str(e)}', exc_info=True)



# Task to calculate actual profit
@shared_task(bind=True)
def actual_member_interest(self,tenant_id,scheme_id,inv_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)
    scheme = get_object_or_404(InvestmentScheme, id=scheme_id)
    # Use reverse relationship b/n staff and contribution to calculate each members contribution relating to the scheme
    members = StaffAPI.objects.filter(
        tenant=tenant,
        investment_scheme=scheme,
        exited_flag=False
    ).annotate(total_contribution=Sum('contribution__total_contribution',filter=Q(contribution__approved_contribution=True,contribution__investment_scheme=scheme), output_field=FloatField()))

    from contributions.models import Membership
    # Get MEMBERSHIPS
    memberships = Membership.objects.filter(
        tenant=tenant,
        scheme=scheme
    )

    inv = InvestmentDetail.objects.get(
                    id=inv_id,
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
    total_contribution = Contribution.objects.filter(investment_scheme__tenant=tenant,investment_scheme=scheme,approved_contribution=True).aggregate(total=Sum('total_contribution'))['total'] or Decimal(0.0)

    logger.info(f'Total: {total_contribution}')

    logger.info('STEP Try')
    try:
        logger.info('STEP 0')
        if total_contribution>0:
            logger.info('STEP 1')
            for member in members:
                # Get membership
                membership = memberships.get(
                    staff=member
                )
                
                # Get member actual amount
                contribution = member.total_contribution or Decimal(0.0)

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
                    membership.total_earnings += interest_on_inv
                    
                    # Subtract interest from member estimated amount
                    membership.estimated_profit = (0-interest_on_inv)
                    membership.save()
                else:
                    logger.info('Not working')
                    membership.total_earnings += Decimal(0.0)
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
            if inv.interest_end_date == timezone.now().date():

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


# Task to calculate and add contribution to user contribution when a contribution is approved
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

        if staff_contribution and staff_contribution>Decimal(0.0):
            staff.contributions += Decimal(staff_contribution) 
            # if staff_contribution else 0.0
            print(f'Staff CONT= {staff_contribution}')
            # append to update list
            staff_updates.append(staff)

    # Using bulk update to effect all changes at once on the contributions field
    if staff_updates:
        StaffAPI.objects.bulk_update(staff_updates,['contributions'])
        logger.info(f'Updated {len(staff_updates)} staffs')
    else:
        logger.infor('No staff contributions to update')



# SCHEDULED PAYOUTS ON DUE DATES + NOTIFY BANK TO PROCESS PAYMENTS
@shared_task(bind=True)
def run_scheduled_payments_and_send_sheet_to_bank_for_payment(self,schedule_payout_date_id):
    # Get filter all due schedule_payment dates
    now = timezone.now().date()
    # Get Scheduled payout date
    try:
        scheduled_date = ScheduledPaymentDates.objects.get(
            id=schedule_payout_date_id
        )   
    except ObjectDoesNotExist:
        logger.error('Scheduled date not found.')
        return
    except Exception as e:
        logger.error(f'An error occured getting schedule dates: {str(e)}')
        return
    
    if not scheduled_date.bank:
        logger.error(f'No bank acssociated with the schedule date: {scheduled_date}')
        return
    

    # scheme = scheduled_date.scheme
    bank = scheduled_date.bank
    percentage = scheduled_date.payout_percentage
    members_on_scheme = Membership.objects.filter(
        tenant=scheduled_date.tenant,
        scheme=scheduled_date.scheme
    )

    if not members_on_scheme.exists():
        logger.info(f'There are no members on this scheme: {scheduled_date.scheme}')
        return

    members_to_be_processed = []
    member_to_update=[]
    total_amount = Decimal(0)
    # Calculate individual payout amount
    for member in members_on_scheme:
        if not member.total_earnings <=Decimal(0):
            payout_amount = Decimal((percentage/Decimal(100))*member.total_earnings)
            member_bank_name = member.staff.bank_name
            member_bank_account_number = member.staff.bank_account_number
            member_bank_branch = member.staff.bank_branch

            member_to_update.append(member)
            members_to_be_processed.append(
                {
                    'bank':member_bank_name,
                    'branch':member_bank_branch,
                    'account_number':member_bank_account_number,
                    'amount':payout_amount
                }
            )
            # keep track of total amount
            total_amount += payout_amount
    
    if members_to_be_processed:
        # Genereate excel sheet
        wb = Workbook()
        sheet = wb.active
        sheet['A1'] = 'Bank'
        sheet['B1'] = 'Branch'
        sheet['C1'] = 'Acc. Number'
        sheet['D1'] = 'Amount'

        for m in members_to_be_processed:
            sheet.append([
                m['bank'],
                m['branch'],
                m['account_number'],
                m['amount']
            ])

        # Add source bank details to sheet
        sheet.append([""]) #Empty row
        sheet.append([""])
        sheet.append(['Total Amount:','',f'{total_amount}'])
        sheet.append(['Source Account:','',f'{bank.account_number}'])
        sheet.append(['Branch:','',f'{bank.branch}'])

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        file_name = f'{scheduled_date.tenant.name}_{scheduled_date.scheme.name}_{scheduled_date.get_month_display()}_{str(now.year)}_SP.xlsx'

        # Create a bank_sheet object for the new file
        try:
            bank_sheet_object = BankSheet.objects.create(
                tenant = scheduled_date.tenant,
                scheme = scheduled_date.scheme,
                name = file_name
            )
        except Exception as e:
            logger.error(f'An error occured creating Bank File object: {str(e)}')
            return

        # Save file to bank sheet object
        bank_sheet_object.excel_file.save(file_name,ContentFile(output.read()), save=True)

        # Get file path
        file_path = bank_sheet_object.excel_file.path if bank_sheet_object.excel_file else None

        if not file_path:
            logger.error('File path not found. Skipping email attachment')
            return
        
        # Send email to bank with attached file
        try:
            email = EmailMessage(
                subject='Request to Pay',
                body='Please find attached file for list of designated payouts.',
                from_email=EMAIL_HOST_USER,
                to=[bank.bank_email,],
            )
            email.attach_file(file_path)
            email.send(fail_silently=False)
            logger.info(f"Email sent successfully to {bank.bank_email} with file {file_name}.")

        except SMTPException as e:
            logger.info(f'Could not send mail due to an SMTP Error: {str(e)}')
            return
        except Exception as e:
            logger.error(f'An error occured while sending mail: {str(e)}')
            return
        
        # After email sent successfully Update all members account balances accordingly
        for m in member_to_update:
            amount = Decimal((percentage/Decimal(100))*m.total_earnings)
            m.total_earnings -= amount
        try:
            with transaction.atomic():
                Membership.objects.bulk_update(member_to_update,['total_earnings'])
            
            logger.info('Member balances updated successfully.')
        except Exception as e:
            logger.error(f'An error occured while updating member balances: {str(e)}')
            return








# NOTIFY 3 DAYS TO SCHEDULED PAYMENT
@shared_task(bind=True)
def notify_tenant_three_days_to_scheduled_payment(self):
    """
    Notify designated staffs about tenants' upcoming payments scheduled in 3 days.
    """
    # Fetch schemes with related scheduled payment dates
    schemes = InvestmentScheme.objects.prefetch_related('scheduledPaymentDate').all()

    for scheme in schemes:
        scheduled_dates = scheme.scheduledPaymentDate.filter(
            approved=True,
        )

        # Tuple to hold messages
        messages_list = []
        
        if scheduled_dates:
            for scheduled_date in scheduled_dates:
                date = timezone.now().date()
                # Get day and month
                day = int(scheduled_date.day)
                month = int(scheduled_date.month)
                logger.info(f'DAY: {day} MONTH: {month}')
                
                week_days, last_day = calendar.monthrange(date.year,month)
                logger.info(f'LAST DAY: {last_day}')

                # check if day is outy of range
                if day > last_day:
                    day = last_day #assign last_day to day

                # generate date using day and month
                try:
                    date = date.replace(day=day, month=month)
                    logger.info(f'DATE: {date}')
                except Exception as e:
                    logger.info(f'INVALID DATE: {e}')
                

                # Call task to process sheet and send to bank for payment
                run_scheduled_payments_and_send_sheet_to_bank_for_payment.delay(
                    schedule_payout_date_id=scheduled_date.id
                )

                # Calculate days until payment
                days_until_payment = (date - timezone.now().date()).days
                if 0 < days_until_payment <= 3:

                    # Get related emails related to the schedule date
                    try:
                        email_list = scheduled_date.tenant.tenant_event_notification.filter(
                                event='upcoming_payment_reminder'
                            ).values_list('staff__email',flat=True)
                    except Exception as e:
                        logger.info('Error Fetching Emails')

                    # create message object
                    message = (
                        'Upcoming Payment Reminder',
                        f'Reminder: Your payment for {scheme.name} is scheduled on {scheduled_date.get_month_display()} {scheduled_date.day}.',
                        EMAIL_HOST_USER,
                        email_list
                    )
                    messages_list.append(message)

            # SEND MASS MAIL TO TENANTS
            try:
                # convert message_list to tuple for mass send mail
                message_tuple = tuple(messages_list)
                # send mass email
                send_mass_mail(
                    message_tuple,
                    fail_silently=False
                )
                logger.info(
                    f'Notification sent successfully.'
                )
            except SMTPException as smtp_error:
                logger.error(
                    f'SMTP Error occured when trying to send mass mail: {smtp_error}'
                )
            except Exception as e:
                logger.error(
                    f'An error occured: {str(e)}'
                )
    


# SEND NOTICE TO BANK TO PROCESS GENERAL PAYMENT
from Member.models import WithdrawalBatch
@shared_task(bind=True)
def send_excel_sheet_to_bank_for_payment(self,batch_id):
    try:
        batches = WithdrawalBatch.objects.filter(
            id__in = batch_id,
            first_approval=True,
            second_approval=True,
            third_approval=True
        ).prefetch_related('withdrawal_request')
    except Exception as e:
        logger.error(f'An error occured: {str(e)}')
        return
    
    if not batches.exists():
        logger.info('No batches found.')
        return

    # List of members to be updated(Balances)
    members_to_be_updated_withdrawals = []
    for batch in batches:
        # Create new sheet for every batch
        new_sheet = Workbook()
        sheet = new_sheet.active
        sheet['A1'] = 'Bank'
        sheet['B1'] = 'Branch'
        sheet['C1'] = 'Acc. Number'
        sheet['D1'] = 'Amount'

        withdrawals = batch.withdrawal_request.all()
        # Get details of every withdrawal and append to worksheet
        if not withdrawals:
            logger.info('No withdrawals found.')
            return
        
        for w in withdrawals:
            bank = w.staff.bank_name
            branch = w.staff.bank_branch
            account_number = w.staff.bank_account_number
            amount = w.amount

            # Append members to be updated to list
            members_to_be_updated_withdrawals.append(w)
            # Append staff details to worksheet
            sheet.append([bank,branch,account_number,amount])
        
        # Add source bank details to sheet
        sheet.append([""]) #Empty row
        sheet.append([""]) #Empty row
        sheet.append(['Total Amount:','',f'{batch.total_amount}'])
        sheet.append(['Source Account:','',f'{batch.bank.account_number}'])
        sheet.append(['Branch:','',f'{batch.bank.branch}'])

        # Generate file path and name
        file_name = f'BP_{batch.id}_invoice.xlsx'

        # convert file to bytes
        output = BytesIO()
        new_sheet.save(output)
        output.seek(0)

        batch.bank_file.save(file_name,ContentFile(output.read()),save=True)


        file_path = batch.bank_file.path if batch.bank_file else None
        if not file_path:
            logger.info('File path not found. Skipping email attachment')
            return

        

        # Send email to bank with attached file
        try:
            email = EmailMessage(
                subject='Request to Pay',
                body='Please find attached file for list of designated payouts.',
                from_email=EMAIL_HOST_USER,
                to=[batch.bank.bank_email,],
            )
            email.attach_file(file_path)
            email.send(fail_silently=False)
            logger.info(f"Email sent successfully to {batch.bank.bank_email} with file {file_name}.")

        except SMTPException as e:
            logger.error(f'Could not send mail due to an SMTP Error: {str(e)}')
            return
        except Exception as e:
            logger.error(f'An error occured while sending mail: {str(e)}')
            return
        
        # Update member balances respectfully.
        try:
            with transaction.atomic():
                for w in members_to_be_updated_withdrawals:
                    membership = w.staff.membership.all().get(scheme=batch.scheme)
                    membership.total_earnings -= w.amount
                    membership.save()
                logger.info(f'Member balances updated successfully for tenant: {batch.tenant.name}')
        except Exception as e:
            logger.error(f'An error occured: {str(e)}')
            return
    logger.info(f'Payment invoice sent to bank. Tenant:{batch.tenant}')
