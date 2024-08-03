from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.contrib import messages
from datetime import datetime
from .decorators import role_required
from .forms import UserForm
import logging

logger = logging.getLogger(__name__)

@login_required
def assign_roles(request):
    tenant = request.tenant
    users = User.objects.filter(tenant = tenant)
    roles = Group.objects.all()
    recent_activities = []

    if request.method == 'POST':
        username = request.POST.get('username')
        role_name = request.POST.get('role')
        try:
            # filterng the user based on the tenant they belong to
            user = User.objects.get(username=username, tenant = tenant)
            role = Group.objects.get(name=role_name)
            user.groups.add(role)
            user.save()
            messages.success(request, f'Role "{role_name}" assigned to user "{username}" successfully.')

            # Record the activity
            activity = f'Admin assigned "{username}" as "{role_name}" on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
            recent_activities.append(activity)

        except User.DoesNotExist and Group.DoesNotExist:
            messages.error(request, 'User does not exist and group does not exist')
        
        return render(request, 'admin_panel/assign_roles.html', {'users': users, 'roles': roles, 'recent_activities': recent_activities})

    return render(request, 'admin_panel/assign_roles.html', {'users': users, 'roles': roles, 'recent_activities': recent_activities})

# Adding User 
@login_required
def add_user(request):
    tenant = request.tenant
    if request.method == 'POST':
        form = UserForm(request.POST)
        form.instance.tenant = tenant
        if form.is_valid():
            form.save()
            return redirect('admin_panel')
    else:
        form = UserForm()
    return render(request, 'admin_panel/add_user.html')

@login_required
def manage_users(request):
    tenant = request.tenant
    users = User.objects.filter(tenant = tenant)
    return render(request, 'admin_panel/manage_users.html', {'users': users})

@login_required
def delete_group(request, group_id):
    group = get_object_or_404(Group)
    group.delete()
    return redirect('admin_panel')

# def profile_view(request):
#     return render(request, 'path/to/profile_template.html')

# Grouped 
@login_required
@role_required('Admin')
def admin_panel(request):
    return render(request, 'admin_panel.html')

@login_required
@role_required('HR')
def hr_page(request):
    return render(request, 'member.html')

@login_required
@role_required('Finance')
def finance_page(request):
    return render(request, 'finance_page.html')


def edit_user_view(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        # handle POST request
        pass  
    return render(request, 'admin_panel/edit_user.html', {'user': user})

def delete_user_view(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        user.delete()
        return redirect('manage_users')  
    return render(request, 'admin_panel/delete_user_confirm.html', {'user': user})

def custom_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            logger.info(f'User {user.username} authenticated successfully.')
            if user.groups.filter(name='Admin').exists():
                logger.info(f'User {user.username} redirected to admin_panel.')
                return redirect('admin_panel')
            elif user.groups.filter(name='HR').exists():
                logger.info(f'User {user.username} redirected to hr_page.')
                return redirect('hr_page')
            elif user.groups.filter(name='Finance').exists():
                logger.info(f'User {user.username} redirected to finance_page.')
                return redirect('finance_page')
            else:
                logger.info(f'User {user.username} redirected to fund.')
                return redirect('fund')
        else:
            messages.error(request, 'Invalid credentials')
            logger.error(f'Authentication failed for username {username}.')
    return render(request, 'login.html')
