
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from functools import wraps

def role_required(role):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            print(f"Checking role for user: {user.username}")
            if user.groups.filter(name=role).exists():
                return view_func(request, *args, **kwargs)
            print(f"User {user.username} does not have the required role: {role}")
            raise PermissionDenied
        return _wrapped_view
    return decorator
