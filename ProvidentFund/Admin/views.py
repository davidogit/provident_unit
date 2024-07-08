# Admin/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import UserForm, RoleForm
from .models import User, Role

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
