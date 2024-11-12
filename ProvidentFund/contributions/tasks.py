from datetime import datetime
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError, Retry
from django.shortcuts import get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
import requests
from django.db import IntegrityError
from dateutil import parser
from django.utils import timezone
from .models import StaffAPI, Contribution
from django.core.exceptions import ValidationError
from MultiScheme.models import Tenant, InvestmentScheme
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, autoretry_for=(requests.exceptions.RequestException,), retry_kwargs={'max_retries': 5, 'countdown': 60})
def fetch_memberships(self):
    try:
        # Get all tenants
        all_tenants = Tenant.objects.all()

        for tenant in all_tenants:
            # loop each scheme and update details accordingly
            api_link = tenant.api_endpoint_contribution

            try:
                # Retrieve data from API
                response = requests.get(api_link)
                response.raise_for_status()  # Raise an error for bad responses
                memberships = response.json()

                # Fetch and update member details
                for membership in memberships:
                    try:
                        incoming_exited_flag = membership.get('exited_flag', False)
                        api_id = membership.get('Id')

                        existing_staff_member = StaffAPI.objects.filter(Id=api_id).first()

                        if existing_staff_member and existing_staff_member.exited_flag:
                            continue

                        if incoming_exited_flag:
                            continue

                        exited_date = membership.get('exited_date', None)
                        if incoming_exited_flag and exited_date:
                            exited_date = timezone.now() if not exited_date else exited_date
                        else:
                            exited_date = None

                        try:

                            # Create or Update staff details
                            staff_member, created = StaffAPI.objects.update_or_create(
                                Id=api_id,
                                tenant=tenant,
                                defaults={
                                    # 'investment_scheme': scheme,
                                    'first_name': membership.get('first_name', ''),
                                    'last_name': membership.get('last_name', ''),
                                    'staff_number': membership.get('staff_number', ''),

                                    'status': membership.get('status', ''),
                                    'fund_type': membership.get('fund_type', ''),
                                    'exited_flag': incoming_exited_flag,

                                }
                            )
                        except IntegrityError:
                            logger.info(f'trying to add a field that already exists')
                        
                            


                        
                        # Adding contributions
                        # Looping through contributions 
                        for contribution_data in membership.get('contributions',[]):

                            # Update contributions to a specific scheme
                            # check if the incoming contribution of a member belongs to the current scheme in loop
                            scheme_id = contribution_data.get('scheme_id')
                            try:
                                scheme = InvestmentScheme.objects.get(id=scheme_id)
                            except ObjectDoesNotExist:
                                logger.info(f'Scheme with id:{scheme_id} not found')
                            

                            # Get staff 
                            staff = StaffAPI.objects.get(Id=api_id)

                            # Validate and parse the contribution date
                            contribution_date = contribution_data.get('contribution_date', '')
                            if contribution_date:
                                try:
                                    contribution_date = datetime.strptime(contribution_date, '%Y-%m-%d').date()
                                except ValueError:
                                    raise ValidationError(f"Invalid date format: {contribution_date}")
                                
                            # create a contribution 
                            Contribution.objects.create(
                                investment_scheme = scheme,
                                member = staff,
                                month = contribution_data['month'],
                                year = contribution_data['year'],
                                employee_amount=contribution_data['employee_amount'],
                                employer_amount=contribution_data['employer_amount'],
                                retro_employee_amount=contribution_data['retro_employee_amount'],
                                retro_employer_amount=contribution_data['retro_employer_amount'],
                                contribution_date=contribution_data['contribution_date'],
                            )
                    except ValidationError as e:
                        print(f'Validation error: {e}')

            except requests.exceptions.RequestException as exc:
                # Retry the task if there's a network error or other request-related issues
                logger.info(f'There was an error contacting server')
                # raise self.retry(exc=exc, countdown=30)
                
    except MaxRetriesExceededError as exc:
        print(f"Max retries exceeded")