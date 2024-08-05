from typing import Any
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.base_user import AbstractBaseUser
from django.http import HttpRequest
from .models import Member


# create a backend to make sure users are mapped to their tenants views
class TenantAwareBackend(ModelBackend):

    def authenticate(self, request: HttpRequest, username: str | None = ..., password: str | None = ..., **kwargs: Any) -> AbstractBaseUser | None:

        # Get tenant from request
        tenant = getattr(request, 'tenant', None)

        if tenant:
            try:
                # We search db for user
                user_profile = Member.objects.get(user__username=username, tenant=tenant)
                if user_profile.user.check_password(password):
                    return user_profile.user
            except Member.DoesNotExist:
                return None

        return None