from datetime import datetime
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError, Retry
from django.shortcuts import get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
import requests
from django.db import IntegrityError
from dateutil import parser
from django.utils import timezone
from .models import StaffAPI, Contribution,Membership
from django.core.exceptions import ValidationError
from MultiScheme.models import Tenant, InvestmentScheme
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

@shared_task(bind=True, autoretry_for=(requests.exceptions.RequestException,), 
             retry_kwargs={'max_retries': 5, 'countdown': 60})
def fetch_memberships(self):
    try:
        all_tenants = Tenant.objects.all()
        # correct_tenant = Tenant.objects.get(id=1)
        for tenant in all_tenants:
            if not tenant.api_endpoint_contribution:
                continue

            try:
                response = requests.get(tenant.api_endpoint_contribution)
                response.raise_for_status()
                memberships = response.json()

                for membership in memberships:
                    try:
                        api_id = membership.get('Id')
                        if not api_id:
                            continue

                        # Staff creation/update
                        staff_member, created = StaffAPI.objects.update_or_create(
                            Id=api_id,
                            tenant=tenant,
                            defaults={
                                'first_name': membership.get('first_name', ''),
                                'last_name': membership.get('last_name', ''),
                                'staff_number': membership.get('staff_number'),
                                'status': membership.get('status', 'active'),
                                'fund_type': membership.get('fund_type'),
                                'exited_flag': membership.get('exited_flag', False)
                            }
                        )

                        # Process contributions
                        for contribution_data in membership.get('contributions', []):
                            scheme_id = contribution_data.get('scheme_id')
                            try:
                                scheme = InvestmentScheme.objects.get(
                                    id=scheme_id,
                                    tenant=tenant,
                                    approved=True
                                )
                            except InvestmentScheme.DoesNotExist:
                                logger.warning(f'Scheme {scheme_id} not found')
                                continue

                            # Create membership record
                            Membership.objects.update_or_create(
                                tenant=tenant,
                                staff=staff_member,
                                scheme=scheme,
                                defaults={
                                    'total_earnings': Decimal('0.00'),
                                    'estimated_profit': Decimal('0.00')
                                }
                            )
                            correct_tenant = Tenant.objects.get(id=1)
                            # Create contribution
                            Contribution.objects.create(
                                tenant=correct_tenant,
                                investment_scheme=scheme,
                                member=staff_member,
                                month=contribution_data['month'],
                                year=contribution_data['year'],
                                employee_amount=Decimal(contribution_data['employee_amount']),
                                employer_amount=Decimal(contribution_data['employer_amount']),
                                retro_employee_amount=Decimal(contribution_data.get('retro_employee_amount', '0.00')),
                                retro_employer_amount=Decimal(contribution_data.get('retro_employer_amount', '0.00')),
                                contribution_date=parser.parse(contribution_data['contribution_date']).date(),
                                approved_contribution=True
                            )

                    except Exception as e:
                        logger.error(f"Error processing member {api_id}: {str(e)}")
                        continue

            except requests.RequestException as e:
                logger.error(f"API request failed for tenant {tenant.id}: {str(e)}")
                raise self.retry(exc=e)

    except Exception as e:
        logger.critical(f"Task failed: {str(e)}")
        raise



# @shared_task(bind=True, autoretry_for=(requests.exceptions.RequestException,), retry_kwargs={'max_retries': 5, 'countdown': 60})
# def fetch_memberships(self):
#     try:
#         # Get all tenants
#         all_tenants = Tenant.objects.all()

#         for tenant in all_tenants:
#             # loop each scheme and update details accordingly
#             api_link = tenant.api_endpoint_contribution

#             try:
#                 # Retrieve data from API
#                 response = requests.get(api_link)
#                 response.raise_for_status()  # Raise an error for bad responses
#                 memberships = response.json()

#                 # Fetch and update member details
#                 for membership in memberships:
#                     try:
#                         incoming_exited_flag = membership.get('exited_flag', False)
#                         api_id = membership.get('Id')

#                         existing_staff_member = StaffAPI.objects.filter(Id=api_id).first()

#                         if existing_staff_member and existing_staff_member.exited_flag:
#                             continue

#                         if incoming_exited_flag:
#                             continue

#                         exited_date = membership.get('exited_date', None)
#                         if incoming_exited_flag and exited_date:
#                             exited_date = timezone.now() if not exited_date else exited_date
#                         else:
#                             exited_date = None

#                         try:

#                             # Create or Update staff details
#                             staff_member, created = StaffAPI.objects.update_or_create(
#                                 Id=api_id,
#                                 tenant=tenant,
#                                 defaults={
#                                     # 'investment_scheme': scheme,
#                                     'first_name': membership.get('first_name', ''),
#                                     'last_name': membership.get('last_name', ''),
#                                     'staff_number': membership.get('staff_number', ''),

#                                     'status': membership.get('status', ''),
#                                     'fund_type': membership.get('fund_type', ''),
#                                     'exited_flag': incoming_exited_flag,

#                                 }
#                             )
#                         except IntegrityError:
#                             logger.info(f'trying to add a field that already exists')
                        
                            


                        
#                         # Adding contributions
#                         # Looping through contributions 
#                         for contribution_data in membership.get('contributions',[]):

#                             # Update contributions to a specific scheme
#                             # check if the incoming contribution of a member belongs to the current scheme in loop
#                             scheme_id = contribution_data.get('scheme_id')
#                             try:
#                                 scheme = InvestmentScheme.objects.get(
#                                     id=scheme_id,
#                                     tenant=tenant,
#                                     approved=True
#                                 )
#                             except ObjectDoesNotExist:
#                                 logger.info(f'Scheme with id:{scheme_id} not found')
#                                 continue
#                             except Exception as e:
#                                 logger.info(f'An error occured: {str(e)}')
                            

#                             # Get staff 
#                             staff = StaffAPI.objects.get(Id=api_id)

#                             # Validate and parse the contribution date
#                             contribution_date = contribution_data.get('contribution_date', '')
#                             if contribution_date:
#                                 try:
#                                     contribution_date = datetime.strptime(contribution_date, '%Y-%m-%d').date()
#                                 except ValueError:
#                                     raise ValidationError(f"Invalid date format: {contribution_date}")
#                                 except Exception as e:
#                                     logger.info(f'An error occured: {str(e)}')
                                
#                             # create a contribution 
#                             Contribution.objects.create(
#                                 investment_scheme = scheme,
#                                 member = staff,
#                                 month = contribution_data['month'],
#                                 year = contribution_data['year'],
#                                 employee_amount=contribution_data['employee_amount'],
#                                 employer_amount=contribution_data['employer_amount'],
#                                 retro_employee_amount=contribution_data['retro_employee_amount'],
#                                 retro_employer_amount=contribution_data['retro_employer_amount'],
#                                 contribution_date=contribution_data['contribution_date'],
#                             )
#                     except ValidationError as e:
#                         logger.info(f'Validation error: {e}')
#                         continue
#                     except Exception as e:
#                         logger.info(f'An error occured: {str(e)}')

#             except requests.exceptions.RequestException as exc:
#                 # Retry the task if there's a network error or other request-related issues
#                 logger.info(f'There was an error contacting server')
#                 # raise self.retry(exc=exc, countdown=30)
#                 continue
#             except Exception as e:
#                 logger.info(f'An error occured: {str(e)}')
#                 continue
                
#     except MaxRetriesExceededError as exc:
#         print(f"Max retries exceeded")
#         return