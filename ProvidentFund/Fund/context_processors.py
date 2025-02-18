# dashboard/context_processors.py
from django.shortcuts import get_object_or_404
from .models import InvestmentScheme
from django.contrib.auth.models import Group,Permission
from django.contrib.auth import get_user_model
# from Admin.models import User

def schemes_processor(request):
    tenant = getattr(request, 'tenant', None)
    schemes = InvestmentScheme.objects.filter(
        tenant=tenant,
        approved=True
    ) if tenant else InvestmentScheme.objects.none()

    delayed_int_option = schemes.filter(delayed_int__in =['Yes',])
    bank_int_option = schemes.filter(bank_int__in =['Yes',])
    return {
        'schemes' : schemes,
        'delayed_int_option': delayed_int_option,
        'bank_int_option' : bank_int_option,
    }


# Making Groups and Permissions globally accessible on all templates

def user_groups_and_permissions(request):
    user = request.user

    # Return early if the user is not authenticated
    if not user.is_authenticated:
        return {}

    # Fetch all group names for the user in a single query
    group_names = set(user.groups.values_list("name", flat=True))

    # Define flags for specific group combinations
    context = {
        # & checks for intersection of groups and bool returns True/False
        # "is_manager_or_treasury_user": bool(group_names & {"Manager", "Treasury User"}),
        # "is_manager_or_hr": bool(group_names & {"Manager", "HR"}),

        # "is_treasury_user": "Treasury User" in group_names,

        # "is_hr_user": "HR" in group_names,

        # "is_manager": "Manager" in group_names,

        # "is_finance_manager": "Finance Manager" in group_names,

        # "is_fund_administrator": "Fund Administrator" in group_names,

        # "is_treasury_administrator": "Treasury Administrator" in group_names,

        """""
        GENERAL USER
        """""
        # User
        "user": user,
        # user linked groups
        "user_groups":user.groups.values_list("name", flat=True),

        """""
        INVESTMENTS
        """""
        # Treasury Manager
        "Treasury_Manager":"Treasury Manager" in group_names,
        # Treasury Supervisor
        "Treasury_Supervisor": "Treasury Supervisor" in group_names,
        # Treasury Analyst
        "Treasury_Analyst": "Treasury Analyst" in group_names,

        """""
        CONTRIBUTIONS
        """""

        # Contributions Manager
        "Contributions_Manager": "Contributions Manager" in group_names,
        # Contributions Supervisor
        "Contributions_Supervisor": "Contributions Supervisor" in group_names,
        # Contributions Analyst
        "Contributions_Analyst": "Contributions Analyst" in group_names,

        """""
        SCHEME MANAGEMENT
        """""
        # Scheme Management
        "Scheme_Manager":"Scheme Manager" in group_names,
        # Scheme Supervisor
        "Scheme_Supervisor": "Scheme Supervisor" in group_names,
        # Scheme Analyst
        "Scheme_Analyst": "Scheme Analyst" in group_names,

        """""
        PAYMENTS
        """""
        # Finance Manager
        "Finance_Manager": "Finance Manager" in group_names,
        # Finance Supervisor
        "Finance_Supervisor": "Finance Supervisor" in group_names,
        # Finance Analyst
        "Finance_Analyst": "Finance Analyst" in group_names,

        """""
        ACCOUNTS SET UP
        """""
        # Super User
        "Super_User": "Super User" in group_names
    }

    return context





###########################################
# def user_groups_and_permissions(request):
#     # tenant = request.tenant
#     user = request.user
#     groups = []
#     # permissions = []

#     # Filter groups and permissions for the user and also check if user is authenticated
#     if user:
#         if user.is_authenticated:
#             if user.groups.exists():
#                 groups = user.groups.all()
#                 # permissions = user.user_permissions.all()
#             # | Permission.objects.filter(group__user=user_instance).distinct()

#                 is_manager_or_treasury_user = groups.filter(name__in=['Manager','Treasury User'])
#                 is_manager_or_hr = groups.filter(name__in=['Manager','HR'])
#                 is_treasury_user = groups.filter(name__in=['Treasury User'])
#                 is_hr_user = groups.filter(name__in=['HR'])
#                 is_manager_user = groups.filter(name__in=['Manager'])
#                 is_finance_manager = groups.filter(name__in=['Finance Manager'])
#                 is_fund_administrator = groups.filter(name__in=['Fund Administrator'])
#                 is_treasury_administrator = groups.filter(name__in=['Treasury Administrator'])

#                 return{
#                     'is_manager_or_treasury_user':is_manager_or_treasury_user,
#                     'is_manager_or_hr':is_manager_or_hr,
#                     'is_treasury_user':is_treasury_user,
#                     'is_hr_user': is_hr_user,
#                     'is_manager' : is_manager_user,
#                     'user':user,
#                     'is_finance_manager': is_finance_manager,
#                     'is_fund_administrator': is_fund_administrator,
#                     'is_treasury_administrator': is_treasury_administrator,
#                 }
#         else:
#             return {}
#     return {}