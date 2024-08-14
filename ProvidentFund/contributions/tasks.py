from datetime import datetime
from celery import shared_task
import requests
from dateutil import parser
from django.utils import timezone
from .models import StaffAPI, Contribution
from django.core.exceptions import ValidationError

@shared_task(bind=True)
def fetch_memberships(self):
    response = requests.get('http://127.0.0.1:8080/api/api/members')
    memberships = response.json()

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

            # Create or Update staff details
            staff_member, created = StaffAPI.objects.update_or_create(
                Id=api_id,
                defaults={
                    'first_name': membership.get('first_name', ''),
                    'last_name': membership.get('last_name', ''),
                    'staff_number': membership.get('staff_number', ''),

                    'status': membership.get('status', ''),
                    'fund_type': membership.get('fund_type', ''),
                    'exited_flag': incoming_exited_flag,

                }
            )

            for contribution_data in membership.get('contributions',[]):
                # Validate and parse the contribution date
                contribution_date = contribution_data.get('contribution_date', '')
                if contribution_date:
                    try:
                        contribution_date = datetime.strptime(contribution_date, '%Y-%m-%d').date()
                    except ValueError:
                        raise ValidationError(f"Invalid date format: {contribution_date}")
                    
                Contribution.objects.update_or_create(
                    member = staff_member,
                    month = contribution_data['month'],
                    year = contribution_data['year'],

                    defaults={
                        'employee_amount': contribution_data['employee_amount'],
                        'employer_amount': contribution_data['employer_amount'],
                        'retro_employee_amount': contribution_data.get('retro_employee_amount', 0),
                        'retro_employer_amount': contribution_data.get('retro_employer_amount', 0),
                        'contribution_date': contribution_data['contribution_date'],
                    }
                )
        except ValidationError as e:
            print(f'Validation error: {e}')

# @shared_task(bind=True)
# def fetch_contributions(self):
#     response = requests.get('https://6697f43902f3150fb66f9865.mockapi.io/api/v1/contribution')
#     contributions = response.json()

#     for contrib in contributions:
#         date_str = contrib['contribution_date']
#         date_obj = parser.parse(date_str) if date_str else None

#         # Get month and year from date
#         month = date_obj.month if date_obj else None
#         year = date_obj.year if date_obj else None

#         # Fetch corresponding member
#         member = StaffAPI.objects.get(Id=contrib['id'])

#         # Only take active members contribution
#         if member.exited_flag == False:        
#             Contribution.objects.update_or_create(
#                 member=member,
#                 month=month,
#                 year=year,
#                 defaults={
#                     'employee_amount': contrib['employee_amount'],
#                     'employer_amount': contrib['employer_amount'],
#                     'retro_employee_amount': contrib['retro_employee_amount'],
#                     'retro_employer_amount': contrib['retro_employer_amount'],
#                     'contribution_date': contrib['contribution_date'],
#                 }
#             )
