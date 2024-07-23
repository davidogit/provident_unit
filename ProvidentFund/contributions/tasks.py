from celery import shared_task
import requests
from dateutil import parser
from django.utils import timezone
from .models import StaffAPI, Contribution

@shared_task(bind=True)
def fetch_memberships():
    response = requests.get('https://66718737e083e62ee43bf829.mockapi.io/api/v1/addmembership')
    memberships = response.json()

    for membership in memberships:
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
                'date_joined': membership.get('date_joined', ''),
                'status': membership.get('status', ''),
                'fund_type': membership.get('fund_type', ''),
                'exited_date': exited_date,
                'exited_flag': incoming_exited_flag,
                'subscription_date': membership.get('subscription_date', ''),
                # 'profit': membership.get('profit', 0),
                # 'updated_date': membership.get('updated_date', ''),
            }
        )

@shared_task(bind=True)
def fetch_contributions():
    response = requests.get('https://6697f43902f3150fb66f9865.mockapi.io/api/v1/contribution')
    contributions = response.json()

    for contrib in contributions:
        date_str = contrib['contribution_date']
        date_obj = parser.parse(date_str) if date_str else None

        # Get month and year from date
        month = date_obj.month if date_obj else None
        year = date_obj.year if date_obj else None

        # Fetch corresponding member
        member = StaffAPI.objects.get(Id=contrib['id'])

        Contribution.objects.update_or_create(
            member=member,
            month=month,
            year=year,
            defaults={
                'employee_amount': contrib['employee_amount'],
                'employer_amount': contrib['employer_amount'],
                'retro_employee_amount': contrib['retro_employee_amount'],
                'retro_employer_amount': contrib['retro_employer_amount'],
                'contribution_date': contrib['contribution_date'],
            }
        )
