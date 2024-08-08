from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
# from .models import User
from django.contrib import messages
from datetime import datetime
from .decorators import role_required
from .forms import UserForm
import logging
# from .forms import EditProfileForm
# from .models import UserProfile 

# Set up logging for debugging and tracking purposes
logger = logging.getLogger(__name__)

User = get_user_model()

# View to assign roles to users
@login_required
@role_required(role=['Admin'])
def assign_roles(request, tenant_id):
    # Retrieve the tenant associated with the request
    tenant = request.tenant

    # Initialize an empty list to track recent activities
    recent_activities = []

    # Fetch users and roles based on the tenant
    users = User.objects.filter(tenant=tenant)  # Get all users associated with the tenant
    roles = Group.objects.all()  # Get all available roles

    # Check if the request method is POST
    if request.method == 'POST':
        # Get the selected username and role from the POST data
        username = request.POST.get('username')
        role_name = request.POST.get('role')

        try:
            # Retrieve the user and role from the database
            person = User.objects.get(username=username)
            group = Group.objects.get(name=role_name)

            # Assign the selected role to the user
            person.groups.add(group)
            person.save()

            # Provide a success message
            messages.success(request, f'Role "{role_name}" assigned to user "{username}" successfully.')

            # Record the activity
            activity = f'Admin assigned "{username}" as "{role_name}" on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
            recent_activities.append(activity)

        except User.DoesNotExist:
            # Handle the case where the user does not exist
            messages.error(request, 'User does not exist')
        except Group.DoesNotExist:
            # Handle the case where the role does not exist
            messages.error(request, 'Group does not exist')

    # Render the assign_roles page with users, roles, and recent activities
    return render(request, 'admin_panel/assign_roles.html', {'users': users, 'roles': roles, 'recent_activities': recent_activities})


# View to add a new user
@login_required
@role_required(role=['Admin'])
def add_user(request, tenant_id):
    # Retrieve the tenant associated with the request
    tenant = request.tenant

    # Check if the request method is POST (indicating form submission)
    if request.method == 'POST':
        # Instantiate the UserForm with the POST data
        form = UserForm(request.POST)
        # Set the tenant for the form instance
        form.instance.tenant = tenant

        # Check if the form data is valid
        if form.is_valid():
            # Save the new user to the database
            form.save()
            # Print form errors for debugging (typically, this should be removed in production)
            print(form.errors)
            # Redirect to the 'admin_roles' view with the tenant_id as a parameter
            return redirect('admin_roles', tenant_id=tenant_id)
    else:
        # Instantiate an empty UserForm for GET requests (form display)
        form = UserForm()

    # Render the 'add_user' template with the form context
    return render(request, 'admin_panel/add_user.html', {'form': form})


# View to manage users
@login_required
@role_required(role=['Admin'])
def manage_users(request, tenant_id):
    tenant = request.tenant
    users = User.objects.filter(tenant=tenant)
    
    # Fetch all roles for the dropdown
    roles = Group.objects.all()
    
    if request.method == 'POST':
        # Handle form submission for editing users
        user_id = request.POST.get('user_id')
        roles = request.POST.getlist('roles')
        user = get_object_or_404(User, id=user_id)
        
        # Clear current roles and add new roles
        user.groups.clear()
        for role_name in roles:
            group = Group.objects.get(name=role_name)
            user.groups.add(group)
        
        # Redirect to the same page or another page after updating
        return redirect('manage_users', tenant_id=tenant_id)
    
    return render(request, 'admin_panel/manage_users.html', {
        'users': users,
        'roles': roles,
    })
# @login_required
# @role_required(role = ['Admin', ])
# def delete_user(request, user_id):
#     user = get_object_or_404(User, id=user_id)
#     user.delete()
#     return HttpResponse(status=204) 

# View to delete a group
@login_required
@role_required(role = ['Admin', ])
def delete_group(request, group_id):
    # Retrieve and delete the group based on ID
    group = get_object_or_404(Group, id=group_id)
    group.delete()
    return redirect('admin_panel')

# View for the admin panel, accessible only by users with the 'Admin' role
@login_required
@role_required(role = ['Admin', 'Customer'])
def admin_panel(request, *args, **kwargs):
    return render(request, 'admin_panel/admin_panel.html')

# View to edit user details
@login_required
@role_required(role = ['Admin',])
def edit_user_view(request, user_id):
    tenant = request.tenant
    user = get_object_or_404(User, id=user_id, tenant=tenant)
    if request.method == 'POST':
        # Handle the POST request to update user details
        pass
    return render(request, 'admin_panel/edit_user.html', {'user': user})


# @login_required
# def view_profile(request):
#     # Retrieve the user's profile information
#     user_profile = UserProfile.objects.get(user=request.user)
#     return render(request, 'profile/view_profile.html', {'user_profile': user_profile})

# @login_required
# def edit_profile(request):
#     if request.method == 'POST':
#         form = UserForm(request.POST, instance=request.user)
#         if form.is_valid():
#             form.save()
#             return redirect('view_profile')  # Redirect to the profile view
#     else:
#         form = UserForm(instance=request.user)
#     return render(request, 'profile/edit_profile.html', {'form': form})

# @login_required
# def help_center(request):
#     return render(request, 'profile/help_center.html')

# @login_required
# def privacy_settings(request):
#     return render(request, 'profile/privacy_settings.html')

# @login_required
# def account_settings(request):
#     return render(request, 'profile/account_settings.html')

# def user_logout(request):
#     logout(request)
#     return redirect('admin_login') 



# Custom login view that sets the tenant context and redirects based on user roles
def custom_login(request, tenant_id):
    request.tenant = tenant_id


    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        


        if user is not None:
            login(request, user)
            logger.info(f'User {user.username} authenticated successfully.')
            # Redirect based on user roles
            if user.groups.filter(name='Admin').exists():  # Check if the user belongs to 'Admin' group
                logger.info(f'User {user.username} redirected to admin_panel.')
                return redirect('admin_panel', tenant_id=tenant_id)
            
            # elif user.groups.filter(name='HR').exists():  # Check if the user belongs to 'HR' group
            #     logger.info(f'User {user.username} redirected to hr_page.')
            #     return redirect('hr_page', tenant_id=tenant_id)
            # elif user.groups.filter(name='Finance').exists():  # Check if the user belongs to 'Finance' group
            #     logger.info(f'User {user.username} redirected to finance_page.')
            #     return redirect('finance_page', tenant_id=tenant_id)

            else:
                logger.info(f'User {user.username} redirected to finance_page.') # redirect to main/general page
                return redirect('finance_page', tenant_id=tenant_id)
        else:
            messages.error(request, 'Invalid credentials')
            logger.error(f'Authentication failed for username {username}.')
    return render(request, 'admin_panel/admin_login.html')


@login_required
def logoutView(request, tenant_id):
    logout(request)
    return redirect('landing_page', tenant_id=tenant_id)