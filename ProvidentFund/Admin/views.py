# Admin/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .forms import UserForm, RoleForm
from django.contrib.auth.models import User, Group
from .models import Role

@login_required
def admin_panel(request):
    return render(request, 'admin_panel/admin_panel.html')

@login_required
def assign_roles(request):
    if request.method == 'POST':
        form = RoleForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('admin_panel')
    else:
        form = RoleForm()
    return render(request, 'admin_panel/assign_roles.html', {'form': form})

@login_required
def add_user(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('admin_panel')
    else:
        form = UserForm()
    return render(request, 'admin_panel/add_user.html', {'form': form})

@login_required
def manage_users(request):
    users = User.objects.all()
    return render(request, 'admin_panel/manage_users.html', {'users': users})

@login_required
def delete_group(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    group.delete()
    return redirect('admin_panel')

def profile_view(request):
   
    return render(request, 'path/to/profile_template.html')

def edit_user_view(request, id):
    user = get_object_or_404(User, id=id)
    if request.method == 'POST':
     
        pass  
    return render(request, 'admin_panel/edit_user.html', {'user': user})

def delete_user_view(request, id):
    user = get_object_or_404(User, id=id)
    if request.method == 'POST':
        user.delete()
        return redirect('manage_users')  
    return render(request, 'admin_panel/delete_user_confirm.html', {'user': user})