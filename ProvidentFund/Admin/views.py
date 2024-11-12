from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from .models import Activity
from django.contrib import messages
from datetime import datetime
# Custom Decorators
from .decorators import role_required
from Member.decorators import unauthenticated_user,tenant_required,tenant_login_required

from .forms import UserForm
import logging
from django.shortcuts import redirect

from MultiScheme.models import Tenant


# Set up logging for debugging and tracking purposes
logger = logging.getLogger(__name__)

User = get_user_model()

# View to assign roles to users
@tenant_login_required
@tenant_required
@role_required(role=['Admin'])
def assign_roles(request, tenant_id):
    # Retrieve the tenant associated with the request
    tenant = get_object_or_404(Tenant, id=tenant_id)
    
    # Fetch users and roles based on the tenant
    users = User.objects.filter(tenant=tenant)
    roles = Group.objects.all()
    
    if request.method == 'POST':
        # Get the selected username and role from the POST data
        username = request.POST.get('username')
        role_name = request.POST.get('role')

        try:
            # Retrieve the user and role from the database
            person = User.objects.get(username=username, tenant=tenant)
            group = Group.objects.get(name=role_name)

            # Assign the selected role to the user
            person.groups.add(group)
            person.save()

            # Record the activity
            Activity.objects.create(
                user=request.user,
                description=f'Assigned "{role_name}" role to user "{username}".'
            )
            
            # Provide a success message
            messages.success(request, f'Role "{role_name}" assigned to user "{username}" successfully.')

            # Redirect to avoid form resubmission
            return redirect('assign_roles', tenant_id=tenant_id)

        except User.DoesNotExist:
            messages.error(request, 'User does not exist or does not belong to the tenant.')
        except Group.DoesNotExist:
            messages.error(request, 'Role does not exist.')

    # Fetch recent activities
    recent_activities = Activity.objects.order_by('-timestamp')[:10]

    # Render the assign_roles page with users, roles, and recent activities
    return render(request, 'admin_panel/assign_roles.html', {
        'users': users,
        'roles': roles,
        'recent_activities': recent_activities
    })

# View to add a new user
@tenant_login_required
@tenant_required
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
            return redirect('assign_roles', tenant_id=tenant_id)
    else:
        # Instantiate an empty UserForm for GET requests (form display)
        form = UserForm()

    # Render the 'add_user' template with the form context
    return render(request, 'admin_panel/add_user.html', {'form': form})


# View to manage users
@tenant_login_required
@tenant_required
@role_required(role=['Admin'])
def manage_users(request, tenant_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)
    users = User.objects.filter(tenant=tenant)
    roles = Group.objects.all()

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        roles_to_add = request.POST.getlist('roles')
        user = get_object_or_404(User, id=user_id, tenant=tenant)
        
        if 'delete_role' in request.POST:
            # Handle deleting a specific role from the user
            role_to_delete = request.POST.get('delete_role')
            group = Group.objects.filter(name=role_to_delete).first()
            if group:
                user.groups.remove(group)
                user.save()
        else:
            # Handle updating roles
            user.groups.clear()
            for role_name in roles_to_add:
                group = Group.objects.filter(name=role_name).first()
                if group:
                    user.groups.add(group)
            user.save()

        return redirect('manage_users', tenant_id=tenant_id)

    return render(request, 'admin_panel/manage_users.html', {
        'tenant': tenant,
        'users': users,
        'roles': roles,
    })



@tenant_login_required
@tenant_required
@role_required(role = ['Admin', ])
def delete_user(request, tenant_id, user_id):
    user = get_object_or_404(User, id=user_id, tenant_id=tenant_id)
    if request.method == 'POST':
        user.delete()
        return redirect('manage_users', tenant_id=tenant_id)  
    

# View to delete a group
@tenant_login_required
@tenant_required
@role_required(role = ['Admin', ])
def delete_group(request, group_id):
    # Retrieve and delete the group based on ID
    group = get_object_or_404(Group, id=group_id)
    group.delete()
    return redirect('admin_panel')

# View for the admin panel, accessible only by users with the 'Admin' role
@tenant_login_required
@tenant_required
@role_required(role = ['Admin', 'Customer'])
def admin_panel(request, *args, **kwargs):
    return render(request, 'admin_panel/admin_panel.html')

@tenant_login_required
@tenant_required
@role_required(role=['Admin'])
def edit_user_view(request, user_id):
    tenant = request.tenant
    user = get_object_or_404(User, id=user_id, tenant=tenant)

    if request.method == 'POST':
        # Check if the delete button was clicked
        if 'delete' in request.POST:
            role_to_delete = request.POST.get('roles')
            group = Group.objects.filter(name=role_to_delete).first()
            if group:
                user.groups.remove(group)

        # Update user roles
        else:
            selected_roles = request.POST.getlist('roles')
            user.groups.set(Group.objects.filter(name__in=selected_roles))
            user.save()

        return redirect('manage_users', tenant_id=tenant.id)  # Redirect to the manage users page

    return render(request, 'admin_panel/edit_user.html', {
        'user': user,
        'roles': Group.objects.all()
    })




# View accessible by both Admin and Customer roles
@tenant_login_required
@role_required(role=['Admin'])
def admin_panel(request, *args, **kwargs):
    # Render the admin panel template
    return render(request, 'admin_panel/admin_panel.html')

# View accessible by Customer role only
# @login_required
# @role_required(role='Customer')
# def customer_view(request, *args, **kwargs):
#     # Render the customer-specific finance page
#     return render(request, 'Fund/templates/dashboard/finance_page.html')

# # View accessible by HR role only
# @login_required
# @role_required(role='HR')
# def finance(request, *args, **kwargs):
#     # Render the HR-specific finance page
#     return render(request, 'Fund/templates/dashboard/finance_page.html')

# Custom login view to authenticate users and redirect them based on their roles
# Admin only login view
@unauthenticated_user
def custom_login(request, tenant_id):
    # Set the tenant context for multi-tenancy
    request.tenant = tenant_id

    tenant = Tenant.objects.get(id=tenant_id)

    if request.method == 'POST':
        # Retrieve the username and password from the POST request
        username = request.POST['username']
        password = request.POST['password']

        # Authenticate the user with the provided credentials
        user = authenticate(request, username=username, password=password)


        user = authenticate(request, username=username, password=password,tenant=tenant)

        # Redirect everyone who is not an admin
        if not user.groups.filter(name='Admin'):
            return redirect('invalid_login_details', tenant_id=tenant_id)
        
        if user is not None:
            # If authentication is successful, log the user in
            login(request, user)
            logger.info(f'User {user.username} authenticated successfully.')

            # Determine the user's group memberships for role-based redirection
            user_groups = user.groups.values_list('name', flat=True)

            if 'Admin' in user_groups:
                # Redirect Admin users to the admin panel
                logger.info(f'User {user.username} redirected to admin_panel.')
            # Check if the user belongs to 'Admin' group
            if user.groups.filter(name='Admin').exists() and user.tenant==tenant:  
                login(request, user)

                return redirect('admin_panel', tenant_id=tenant_id)
            # elif 'HR' in user_groups:
            #     # Redirect HR users to their dashboard
            #     logger.info(f'User {user.username} redirected to finance_page.')
            #     return redirect('finance_page', tenant_id=tenant_id)
            # elif 'Customer' in user_groups:
            #     # Redirect Customer users to their dashboard
            #     logger.info(f'User {user.username} redirected to customer_view.')
            #     return redirect('customer_view', tenant_id=tenant_id)

            else:
                # If the user doesn't belong to a specific group, redirect to a default page
                logger.info(f'User {user.username} does not belong to a specific group, redirecting to a default page.')
                return redirect('finance_page', tenant_id=tenant_id)
                #  Redirect to invalid_login_details view
                return redirect('access_denied', tenant_id=tenant_id)
        else:
            # If authentication fails, display an error message
            messages.error(request, 'Invalid credentials')
            logger.error(f'Authentication failed for username {username}.')

    # Render the login page if the request method is GET
            # Redirect to invalid_login_details view
            return redirect('invalid_login_details', tenant_id=tenant_id)
        
    return render(request, 'admin_panel/admin_login.html')


@tenant_login_required
def logoutView(request, tenant_id):
    logout(request)
    return redirect('landing_page', tenant_id=tenant_id)