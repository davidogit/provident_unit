# # tasks.py
# from celery import shared_task
# import requests
# from django.utils import timezone
# from django.db.models import Sum, F
# from .models import StaffAPI, Contribution

# @shared_task
# def update_total_contributions():
#     staff_members = StaffAPI.objects.all()

#     for staff_member in staff_members:
#         total_contributions = staff_member.contributions.aggregate(
#             total=Sum(
#                 F('EmployeeAmount') + 
#                 F('EmployerAmount') + 
#                 F('RetroEmployeeAmount') + 
#                 F('RetroEmployerAmount')
#             )
#         )['total'] or 0
        
#         # If StaffAPI model doesn't have the total_contributions field, compute dynamically
#         # No need to save it to the database
#         staff_member.total_contributions = total_contributions
#         # Uncomment the line below if you need to save it to the database
#         # staff_member.save()

#     return "Total contributions updated for all staff members."

# @shared_task
# def update_staffapi_members():
#     response = requests.get('https://66718737e083e62ee43bf829.mockapi.io/api/v1/addmembership')
#     memberships = response.json()

#     for membership in memberships:
#         incoming_exited_flag = membership.get('ExitedFlag', False)
#         api_id = membership.get('Id')

#         # Fetch the existing staff member if exists
#         existing_staff_member = StaffAPI.objects.filter(Id=api_id).first()

#         # Check if the existing or incoming ExitedFlag is True
#         if existing_staff_member and existing_staff_member.ExitedFlag:
#             continue  # Skip update or create if existing ExitedFlag is True

#         if incoming_exited_flag:
#             continue  # Skip update or create if incoming ExitedFlag is True

#         # Proceed to update or create if checks pass
#         ExitedDate = membership.get('ExitedDate', None)
#         if incoming_exited_flag and ExitedDate:
#             ExitedDate = timezone.now() if not ExitedDate else ExitedDate
#         else:
#             ExitedDate = None
#         staff_member, created = StaffAPI.objects.update_or_create(
#             Id=api_id,
#             defaults={
#                 'Fullname': membership.get('Fullname', ''),
#                 'Staffnumber': membership.get('Staffnumber', ''),
#                 'Datejoined': membership.get('Datejoined', ''),
#                 'status': membership.get('status', ''),
#                 'Fundtype': membership.get('Fundtype', ''),
#                 'EmployeeAmount': membership.get('EmployeeAmount', 0.0),
#                 'EmployerAmount': membership.get('EmployerAmount', 0.0),
#                 'RetroEmployeeAmount': membership.get('RetroEmployeeAmount', 0.0),
#                 'RetroEmployerAmount': membership.get('RetroEmployerAmount', 0.0),
#                 'ContributionDate': membership.get('ContributionDate', ''),
#                 'ExitedDate': ExitedDate,
#                 'ExitedFlag': incoming_exited_flag,
#              }
#         )

#         # Update the contribution details
#         if 'contributions' in membership:
#             for contrib in membership['contributions']:
#                 Contribution.objects.update_or_create(
#                     member=staff_member,
#                     month=contrib['month'],
#                     year=contrib['year'],
#                     defaults={
#                         'EmployeeAmount': contrib['EmployeeAmount'],
#                         'EmployerAmount': contrib['EmployerAmount'],
#                         'RetroEmployeeAmount': contrib['RetroEmployeeAmount'],
#                         'RetroEmployerAmount': contrib['RetroEmployerAmount'],
#                         'ContributionDate': contrib['ContributionDate'],
#                     }
#                 )

#     return "StaffAPI members updated from external API."
