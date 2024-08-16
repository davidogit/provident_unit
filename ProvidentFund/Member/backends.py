from typing import Any
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.base_user import AbstractBaseUser
from django.http import HttpRequest
from django.shortcuts import redirect, render
from .models import Member
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist


# create a backend to make sure users are mapped to their tenants views
class TenantAwareBackend(ModelBackend):

    def authenticate(self, request: HttpRequest, username: str | None = ..., password: str | None = ...,tenant=None,  **kwargs: Any) -> AbstractBaseUser | None:

        UserModel = get_user_model()

        try:
            # We search db for user
            user = UserModel.objects.get(username=username,tenant=tenant)
            if user.check_password(password):
                return user
        except UserModel.DoesNotExist:
            return None
        # redirect('invalid_login_details', tenant_id=tenant)

    def get_user(self,user_id):
        UserModel = get_user_model()
        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None