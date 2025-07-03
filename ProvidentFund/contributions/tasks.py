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
from contributions.models import Contribution, Membership
from Member.models import StaffAPI
import logging
from decimal import Decimal, InvalidOperation
from decimal import Decimal, InvalidOperation
from datetime import datetime


logger = logging.getLogger(__name__)

@shared_task(bind=True, autoretry_for=(requests.exceptions.RequestException,), 
             retry_kwargs={'max_retries': 5, 'countdown': 60})
def fetch_memberships(self):
    """
    Fetch member and contribution data from separate tenant API endpoints.
    Compatible with your actual database models.
    """
    try:
        all_tenants = Tenant.objects.all()
        logger.info(f"Found {all_tenants.count()} tenants to process")
        
        for tenant in all_tenants:
            # Check if tenant has both required endpoints
            if not tenant.api_endpoint_member or not tenant.api_endpoint_contribution:
                logger.warning(f"Tenant {tenant.id} missing required API endpoints. "
                             f"Member: {bool(tenant.api_endpoint_member)}, "
                             f"Contribution: {bool(tenant.api_endpoint_contribution)}")
                continue

            try:
                logger.info(f"Processing tenant {tenant.id} - {tenant.name}")
                logger.info(f"Member endpoint: {tenant.api_endpoint_member}")
                logger.info(f"Contribution endpoint: {tenant.api_endpoint_contribution}")
                
                # Step 1: Fetch and process member data
                member_data = fetch_member_data(tenant)
                if not member_data:
                    logger.error(f"Failed to fetch member data for tenant {tenant.id}")
                    continue
                
                processed_members = process_member_data(member_data, tenant)
                logger.info(f"Processed {len(processed_members)} members for tenant {tenant.id}")
                
                # Step 2: Fetch and process contribution data
                contribution_data = fetch_contribution_data(tenant)
                if not contribution_data:
                    logger.error(f"Failed to fetch contribution data for tenant {tenant.id}")
                    continue
                
                processed_contributions = process_contribution_data(
                    contribution_data, processed_members, tenant
                )
                logger.info(f"Processed {processed_contributions} contributions for tenant {tenant.id}")

            except requests.RequestException as e:
                logger.error(f"API request failed for tenant {tenant.id}: {str(e)}")
                raise self.retry(exc=e)
            except Exception as e:
                logger.error(f"Unexpected error processing tenant {tenant.id}: {str(e)}")
                logger.exception("Full traceback:")  # This will show the full error
                continue

        logger.info("Task completed successfully")
        return "Task completed"

    except Exception as e:
        logger.critical(f"Task failed with critical error: {str(e)}")
        logger.exception("Full critical error traceback:")
        raise

def fetch_member_data(tenant):
    """
    Fetch member data from the member endpoint.
    Returns list of member records or None if failed.
    """
    try:
        logger.info(f"Fetching member data for tenant {tenant.id} from {tenant.api_endpoint_member}")
        response = requests.get(
            tenant.api_endpoint_member,
            timeout=30,
            headers={'Content-Type': 'application/json'}
        )
        logger.info(f"Response status: {response.status_code}")
        response.raise_for_status()
        
        member_data = response.json()
        logger.info(f"Raw response type: {type(member_data)}")
        
        # Handle paginated response from DRF
        if isinstance(member_data, dict) and 'results' in member_data:
            member_data = member_data['results']
            logger.info("Extracted results from paginated response")
        
        if not isinstance(member_data, list):
            logger.error(f"Expected list of members from tenant {tenant.id}, got {type(member_data)}")
            logger.error(f"Response content: {member_data}")
            return None
            
        logger.info(f"Retrieved {len(member_data)} member records for tenant {tenant.id}")
        return member_data
        
    except ValueError as e:
        logger.error(f"Invalid JSON in member response from tenant {tenant.id}: {str(e)}")
        return None
    except requests.RequestException as e:
        logger.error(f"Member API request failed for tenant {tenant.id}: {str(e)}")
        raise

def fetch_contribution_data(tenant):
    """
    Fetch contribution data from the contribution endpoint.
    Returns list of contribution records or None if failed.
    """
    try:
        logger.info(f"Fetching contribution data for tenant {tenant.id} from {tenant.api_endpoint_contribution}")
        response = requests.get(
            tenant.api_endpoint_contribution,
            timeout=30,
            headers={'Content-Type': 'application/json'}
        )
        logger.info(f"Response status: {response.status_code}")
        response.raise_for_status()
        
        contribution_data = response.json()
        logger.info(f"Raw response type: {type(contribution_data)}")
        
        # Handle paginated response from DRF
        if isinstance(contribution_data, dict) and 'results' in contribution_data:
            contribution_data = contribution_data['results']
            logger.info("Extracted results from paginated response")
        
        if not isinstance(contribution_data, list):
            logger.error(f"Expected list of contributions from tenant {tenant.id}, got {type(contribution_data)}")
            logger.error(f"Response content: {contribution_data}")
            return None
            
        logger.info(f"Retrieved {len(contribution_data)} contribution records for tenant {tenant.id}")
        return contribution_data
        
    except ValueError as e:
        logger.error(f"Invalid JSON in contribution response from tenant {tenant.id}: {str(e)}")
        return None
    except requests.RequestException as e:
        logger.error(f"Contribution API request failed for tenant {tenant.id}: {str(e)}")
        raise

def process_member_data(member_data, tenant):
    """
    Process member data and create/update member records.
    Returns dictionary mapping member IDs to member objects.
    """
    processed_members = {}
    success_count = 0
    error_count = 0
    
    logger.info(f"Processing {len(member_data)} member records")
    
    for member_record in member_data:
        try:
            if not isinstance(member_record, dict):
                logger.warning(f"Invalid member record type: {type(member_record)}")
                error_count += 1
                continue
            
            # Your model uses 'Id' as primary key field
            member_id = member_record.get('Id') or member_record.get('id')
            if not member_id:
                logger.warning(f"Member record missing required 'Id' field: {member_record}")
                error_count += 1
                continue
            
            logger.debug(f"Processing member {member_id}")
            
            # Create or update member - matching your StaffAPI model fields
            member_defaults = {
                'first_name': member_record.get('first_name', ''),
                'last_name': member_record.get('last_name', ''),
                'staff_number': member_record.get('staff_number'),
                'status': member_record.get('status', 'active'),
                'fund_type': member_record.get('fund_type'),
                'exited_flag': member_record.get('exited_flag', False),
                # Additional fields from your model
                'subscription_date': member_record.get('subscription_date'),
                'bank_name': member_record.get('bank_name', ''),
                'bank_branch': member_record.get('bank_branch', ''),
                'bank_account_number': member_record.get('bank_account_number', ''),
            }
            
            # Parse subscription_date if it exists
            if member_record.get('subscription_date'):
                try:
                    member_defaults['subscription_date'] = parser.parse(
                        member_record['subscription_date']
                    ).date()
                except (ValueError, TypeError):
                    member_defaults['subscription_date'] = None
            
            staff_member, created = StaffAPI.objects.update_or_create(
                Id=member_id,
                tenant=tenant,
                defaults=member_defaults
            )
            
            # Handle investment schemes (ManyToMany relationship)
            if 'investment_schemes' in member_record:
                scheme_ids = member_record['investment_schemes']
                if isinstance(scheme_ids, list):
                    schemes = InvestmentScheme.objects.filter(
                        id__in=scheme_ids,
                        tenant=tenant,
                        approved=True
                    )
                    staff_member.investment_scheme.set(schemes)
            
            processed_members[str(member_id)] = staff_member
            success_count += 1
            
            if created:
                logger.debug(f"Created new member {member_id} for tenant {tenant.id}")
            else:
                logger.debug(f"Updated member {member_id} for tenant {tenant.id}")
                
        except Exception as e:
            logger.error(f"Error processing member record {member_record.get('Id', 'unknown')}: {str(e)}")
            logger.exception("Member processing error:")
            error_count += 1
            continue
    
    logger.info(f"Member processing complete for tenant {tenant.id}. "
               f"Success: {success_count}, Errors: {error_count}")
    
    return processed_members

def process_contribution_data(contribution_data, processed_members, tenant):
    """
    Process contribution data and create contribution records.
    Returns count of successfully processed contributions.
    """
    success_count = 0
    error_count = 0
    
    logger.info(f"Processing {len(contribution_data)} contribution records")
    
    for contribution_record in contribution_data:
        try:
            if not isinstance(contribution_record, dict):
                logger.warning(f"Invalid contribution record type: {type(contribution_record)}")
                error_count += 1
                continue
            
            # Get the member ID - your API might use different field names
            member_id = (contribution_record.get('member') or 
                        contribution_record.get('member_id') or 
                        contribution_record.get('staff_id') or
                        contribution_record.get('Id'))
            
            if not member_id:
                logger.warning(f"Contribution record missing member/staff ID: {contribution_record}")
                error_count += 1
                continue
            
            logger.debug(f"Processing contribution for member {member_id}")
            
            # Find the corresponding member
            staff_member = processed_members.get(str(member_id))
            if not staff_member:
                logger.warning(f"Member {member_id} not found for contribution record")
                error_count += 1
                continue
            
            # Process the contribution
            if create_single_contribution(contribution_record, staff_member, tenant):
                success_count += 1
            else:
                error_count += 1
                
        except Exception as e:
            logger.error(f"Error processing contribution record: {str(e)}")
            logger.exception("Contribution processing error:")
            error_count += 1
            continue
    
    logger.info(f"Contribution processing complete for tenant {tenant.id}. "
               f"Success: {success_count}, Errors: {error_count}")
    
    return success_count

def create_single_contribution(contribution_data, staff_member, tenant):
    """
    Create a single contribution record matching your Contribution model.
    Returns True if successful, False otherwise.
    """
    try:
        # Get investment scheme - your model has investment_scheme field
        scheme_id = contribution_data.get('investment_scheme') or contribution_data.get('scheme_id')
        if not scheme_id:
            logger.warning(f"Missing investment_scheme ID for member {staff_member.Id}")
            return False
        
        try:
            scheme = InvestmentScheme.objects.get(
                id=scheme_id,
                tenant=tenant,
                approved=True
            )
        except InvestmentScheme.DoesNotExist:
            logger.warning(f'Scheme {scheme_id} not found for tenant {tenant.id}')
            return False
        
        # Parse contribution date
        contribution_date = None
        if contribution_data.get('contribution_date'):
            try:
                contribution_date = parser.parse(contribution_data['contribution_date']).date()
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid contribution_date format: {str(e)}")
                return False
        else:
            # Use current date if not provided
            contribution_date = datetime.now().date()
        
        # Convert amounts to Decimal - handle your model fields
        try:
            employee_amount = Decimal(str(contribution_data.get('employee_amount', '0.00')))
            employer_amount = Decimal(str(contribution_data.get('employer_amount', '0.00')))
            retro_employee_amount = Decimal(str(contribution_data.get('retro_employee_amount', '0.00')))
            retro_employer_amount = Decimal(str(contribution_data.get('retro_employer_amount', '0.00')))
        except (ValueError, TypeError, InvalidOperation) as e:
            logger.warning(f"Invalid decimal values in contribution data: {str(e)}")
            return False
        
        # Your Contribution model automatically calculates month/year from contribution_date
        # Check for existing contribution to avoid duplicates
        existing_contribution = Contribution.objects.filter(
            investment_scheme=scheme,
            member=staff_member,
            contribution_date=contribution_date
        ).first()
        
        if existing_contribution:
            logger.debug(f"Contribution already exists for member {staff_member.Id}, "
                        f"scheme {scheme_id}, date {contribution_date}")
            return True
        
        # Create the contribution - matching your model structure
        contribution = Contribution.objects.create(
            investment_scheme=scheme,
            member=staff_member,
            employee_amount=employee_amount,
            employer_amount=employer_amount,
            retro_employee_amount=retro_employee_amount,
            retro_employer_amount=retro_employer_amount,
            contribution_date=contribution_date,
            approved_contribution=contribution_data.get('approved_contribution', True)
        )
        
        # Create/update membership record
        Membership.objects.update_or_create(
            tenant=tenant,
            staff=staff_member,
            scheme=scheme,
            defaults={
                'total_earnings': Decimal('0.00'),
                'estimated_profit': Decimal('0.00')
            }
        )
        
        logger.debug(f"Created contribution for member {staff_member.Id}, scheme {scheme_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error creating contribution for member {staff_member.Id}: {str(e)}")
        logger.exception("Contribution creation error:")
        return False



# @shared_task(bind=True, autoretry_for=(requests.exceptions.RequestException,), 
#              retry_kwargs={'max_retries': 5, 'countdown': 60})
# def fetch_memberships(self):
#     try:
#         all_tenants = Tenant.objects.all()
#         # correct_tenant = Tenant.objects.get(id=1)
#         for tenant in all_tenants:
#             if not tenant.api_endpoint_contribution:
#                 continue

#             try:
#                 response = requests.get(tenant.api_endpoint_contribution)
#                 response.raise_for_status()
#                 memberships = response.json()

#                 for membership in memberships:

                
#                     api_id = 'unknown' # <-- Safe fallback



#                     try:
#                         if not isinstance(membership, dict):
#                             raise TypeError(f"Expected dict, got {type(membership)}")
                        
#                         print("DEBUG response JSON:", memberships)
#                         logger.error(f"Unexpected response structure: {memberships}")

                        
#                         api_id = membership.get('Id')
#                         if not api_id:
#                             continue

#                         # Staff creation/update
#                         staff_member, created = StaffAPI.objects.update_or_create(
#                             Id=api_id,
#                             tenant=tenant,
#                             defaults={
#                                 'first_name': membership.get('first_name', ''),
#                                 'last_name': membership.get('last_name', ''),
#                                 'staff_number': membership.get('staff_number'),
#                                 'status': membership.get('status', 'active'),
#                                 'fund_type': membership.get('fund_type'),
#                                 'exited_flag': membership.get('exited_flag', False)
#                             }
#                         )

#                         # Process contributions
#                         for contribution_data in membership.get('contributions', []):
#                             scheme_id = contribution_data.get('scheme_id')
#                             try:
#                                 scheme = InvestmentScheme.objects.get(
#                                     id=scheme_id,
#                                     tenant=tenant,
#                                     approved=True
#                                 )
#                             except InvestmentScheme.DoesNotExist:
#                                 logger.warning(f'Scheme {scheme_id} not found')
#                                 continue

#                             # Create membership record
#                             Membership.objects.update_or_create(
#                                 tenant=tenant,
#                                 staff=staff_member,
#                                 scheme=scheme,
#                                 defaults={
#                                     'total_earnings': Decimal('0.00'),
#                                     'estimated_profit': Decimal('0.00')
#                                 }
#                             )
#                             # correct_tenant = Tenant.objects.get(id=1)
#                             correct_tenant = tenant
#                             # Create contribution
#                             Contribution.objects.create(
#                                 tenant=tenant,
#                                 investment_scheme=scheme,
#                                 member=staff_member,
#                                 month=contribution_data['month'],
#                                 year=contribution_data['year'],
#                                 employee_amount=Decimal(contribution_data['employee_amount']),
#                                 employer_amount=Decimal(contribution_data['employer_amount']),
#                                 retro_employee_amount=Decimal(contribution_data.get('retro_employee_amount', '0.00')),
#                                 retro_employer_amount=Decimal(contribution_data.get('retro_employer_amount', '0.00')),
#                                 contribution_date=parser.parse(contribution_data['contribution_date']).date(),
#                                 approved_contribution=True
#                             )

#                     except Exception as e:
#                         logger.error(f"Error processing member {api_id}: {str(e)}")
#                         continue

#             except requests.RequestException as e:
#                 logger.error(f"API request failed for tenant {tenant.id}: {str(e)}")
#                 raise self.retry(exc=e)

#     except Exception as e:
#         logger.critical(f"Task failed: {str(e)}")
#         raise



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