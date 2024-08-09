from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from functools import wraps
from django.http import HttpResponse

# A decorator to check if the user has the required role
def role_required(role = []):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = request.user  # Get the current user from the request

            if not user.is_authenticated:
                # print(f"User is not authenticated.")
                return render(request, 'dashboard/access_denied.html')

            # print(f"Checking role for user: {user.username}")  # Debug print statement

            if not user.groups.exists():
                print(f"User {user.username} does not belong to any group.")
                return render(request, 'dashboard/access_denied.html')

            group = user.groups.first().name  # Get the first group name
            print(f"User group: {group}")
            print(f"Required role: {role}")

            if group in role:
                return view_func(request, *args, **kwargs)  # Call the view function if the role matches
            else:
                return render(request, 'dashboard/access_denied.html')

        return _wrapped_view
    return decorator
