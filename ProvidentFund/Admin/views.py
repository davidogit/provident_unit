from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
# from .models import User
from django.contrib import messages
from datetime import datetime
from .decorators import role_required
from .forms import UserForm
import logging

# Set up logging for debugging and tracking purposes
logger = logging.getLogger(__name__)

User = get_user_model()

# View to assign roles to users
@login_required
@role_required(role = ['Admin',])
def assign_roles(request, tenant_id):
    
    # Get the tenant from the request to filter users by tenant
    tenant = request.tenant
    # Retrieve users and roles based on the tenant
    # user = User.objects.filter(tenant=tenant)
    # role = Group.objects.all()  # Get all groups (roles)
    recent_activities = []

    user = User.objects.filter(tenant=tenant)
    role = Group.objects.all()

    if request.method == 'POST':
        username = request.POST.get('username')
        role_name = request.POST.get('role')
    
        person = User.objects.get(username = username)
        group = Group.objects.get(name = role_name)

        try:
            # Find the user and role based on the tenant
           
            # Add the role to the user
            person.groups.add(group)  # This uses `user.groups` which refers to the groups the user is part of
            person.save()
            # Show success message
            messages.success(request, f'Role "{role_name}" assigned to user "{username}" successfully.')

            # Record the activity
            activity = f'Admin assigned "{username}" as "{role_name}" on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
            recent_activities.append(activity)

        except User.DoesNotExist:
            # Show error message if user or role does not exist
            messages.error(request, 'User does not exist')
        except Group.DoesNotExist:
            # show error message if user or role does not exist
            messages.error(request, 'Group does not exist')

    # Initial render of the page
    return render(request, 'admin_panel/assign_roles.html', {'users': user, 'roles': role, 'recent_activities': recent_activities})

# View to add a new user
@login_required
@role_required(role = ['Admin',])
def add_user(request, tenant_id):
    tenant = request.tenant
    if request.method == 'POST':
        form = UserForm(request.POST)
        form.instance.tenant = tenant
        if form.is_valid():
            form.save()
            print(form.errors)
            return redirect('admin_panel')
    else:
        form = UserForm()
    return render(request, 'admin_panel/add_user.html', {'form': form})

# View to manage users
@login_required
@role_required(role = ['Admin',])
def manage_users(request, tenant_id):
    tenant = request.tenant
    users = User.objects.filter(tenant=tenant)
    return render(request, 'admin_panel/manage_users.html', {'users': users})

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

# View to delete a user
@login_required
@role_required(role = ['Admin', ])
def delete_user_view(request, user_id):
    tenant = request.tenant
    user = get_object_or_404(User, id=user_id, tenant=tenant)
    if request.method == 'POST':
        user.delete()
        return redirect('manage_users')
    return render(request, 'admin_panel/delete_user_confirm.html', {'user': user})

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
