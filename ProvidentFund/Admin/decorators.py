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
                # User is not authenticated
                return render(request, 'dashboard/access_denied.html')

            # Checks if the user belongs to any of the required roles
            if not any(group.name in role for group in user.groups.all()):
                # User does not have the required role
                return redirect('access_denied', tenant_id=request.tenant.id)

            # User has the required role, proceed to the view
            return view_func(request, *args, **kwargs)

        return _wrapped_view
    return decorator
