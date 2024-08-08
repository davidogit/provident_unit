from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from functools import wraps
from django.http import HttpResponse

# A decorator to check if the user has the required role
def role_required(role = []):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = request.user  # Get the current user from the request

            if not user.is_authenticated:
                print(f"User is not authenticated.")
                return HttpResponse("You must be logged in to access this page.")

            print(f"Checking role for user: {user.username}")  # Debug print statement

            if not user.groups.exists():
                print(f"User {user.username} does not belong to any group.")
                return HttpResponse("Access Denied!")

            group = user.groups.first().name  # Get the first group name
            print(f"User group: {group}")
            print(f"Required role: {role}")

            if group in role:
                return view_func(request, *args, **kwargs)  # Call the view function if the role matches
            else:
                return HttpResponse("Access Denied!")

        return _wrapped_view
    return decorator
