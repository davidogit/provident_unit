
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required

def role_required(role_name):
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return login_required(view_func)(request, *args, **kwargs)
            if not request.user.groups.filter(name=role_name).exists():
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
