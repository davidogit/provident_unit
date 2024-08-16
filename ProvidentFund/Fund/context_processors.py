# # dashboard/context_processors.py
# from django.shortcuts import get_object_or_404
# from .models import InvestmentScheme
# from django.contrib.auth.models import Group,Permission
# from django.contrib.auth import get_user_model
# # from Admin.models import User

# def schemes_processor(request):
#     tenant = getattr(request, 'tenant', None)
#     schemes = InvestmentScheme.objects.filter(tenant=tenant) if tenant else []
#     return {
#         'schemes': schemes
#     }


# # Making Groups and Permissions globally accessible on all templates

# def user_groups_and_permissions(request):
#     user = request.user  # Get the current user from the request
#     groups = []  # Initialize an empty list for groups
#     context = {}  # Initialize an empty dictionary to store context data

#     # Check if the user is authenticated
#     if user and user.is_authenticated:
#         # Fetch all groups the user belongs to
#         groups = user.groups.all()

#         # Check if the user is part of specific groups
#         is_manager_or_treasury_user = groups.filter(name__in=['Manager', 'Treasury User']).exists()
#         is_manager_or_hr = groups.filter(name__in=['Manager', 'HR']).exists()
#         is_treasury_user = groups.filter(name__in=['Treasury User']).exists()
#         is_hr_user = groups.filter(name__in=['HR']).exists()
#         is_manager_user = groups.filter(name='Manager').exists()

#         # Update the context dictionary with the results
#         context.update({
#             'is_manager_or_treasury_user': is_manager_or_treasury_user,  # True if user is in Manager or Treasury User group
#             'is_manager_or_hr': is_manager_or_hr,  # True if user is in Manager or HR group
#             'is_treasury_user': is_treasury_user,  # True if user is in Treasury User group
#             'is_hr_user': is_hr_user,  # True if user is in HR group
#             'is_manager': is_manager_user,  # True if user is in Manager group
#             'user': user,  # Add the user object to the context
#         })
    
#     # Always return the context dictionary, even if empty
#     return context



 # dashboard/context_processors.py
from django.shortcuts import get_object_or_404
from .models import InvestmentScheme
from django.contrib.auth.models import Group,Permission
from django.contrib.auth import get_user_model
# from Admin.models import User

def schemes_processor(request):
    tenant = getattr(request, 'tenant', None)
    schemes = InvestmentScheme.objects.filter(tenant=tenant) if tenant else []
    return {
        'schemes': schemes
    }


# Making Groups and Permissions globally accessible on all templates

def user_groups_and_permissions(request):
    # tenant = request.tenant
    user = request.user
    groups = []
    # permissions = []

    # Filter groups and permissions for the user and also check if user is authenticated
    if user:
        if user.is_authenticated:
            if user.groups.exists():
                groups = user.groups.all()
                # permissions = user.user_permissions.all()
            # | Permission.objects.filter(group__user=user_instance).distinct()

                is_manager_or_treasury_user = groups.filter(name__in=['Manager','Treasury User'])
                is_manager_or_hr = groups.filter(name__in=['Manager','HR'])
                is_treasury_user = groups.filter(name__in=['Treasury User'])
                is_hr_user = groups.filter(name__in=['HR'])
                is_manager_user = groups.filter(name__in=['Manager'])

                return{
                    'is_manager_or_treasury_user':is_manager_or_treasury_user,
                    'is_manager_or_hr':is_manager_or_hr,
                    'is_treasury_user':is_treasury_user,
                    'is_hr_user': is_hr_user,
                    'is_manager' : is_manager_user,
                    'user':user,
                }
        # Always return an empty dictionary if no conditions are met
            return {}
