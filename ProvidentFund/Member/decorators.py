from django.http import HttpResponseRedirect,HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from MultiScheme.models import Tenant

# This decorator is to prevent users from accessing login and register views while alredy logged in 
def unauthenticated_user(view_func):
    def wrapper_func(request,*args,**kwargs):
        # Checking if user is already logged in
        if request.user.is_authenticated:
            # We use reverse to get a url and then use HttpResponseRedirect to send us to that url
            url = reverse('finance_page', kwargs={'tenant_id':request.tenant.id})
            return HttpResponseRedirect(url)
        else:
            return view_func(request,*args,**kwargs)
    return wrapper_func


# Ensures the user trying to access a view belongs to the tenant of that view
from functools import wraps
# from django.http import HttpResponseForbidden

def tenant_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        tenant_id = kwargs.get('tenant_id')
        tenant = Tenant.objects.get(id=tenant_id)
        print(request.user.tenant)
        if request.user.is_authenticated and request.user.tenant == tenant:
            return view_func(request, *args, **kwargs)
        return redirect('invalid_login_details', tenant_id=request.user.tenant.id)
    # HttpResponseForbidden("You do not have permission to access this page 11.")

    return _wrapped_view











# This decorator is to check the group of the user and give access accordingly
def allowed_user(allowed_groups=[]):
    def allowed_user_dec(view_func):
        def wrapper_func(request,*args,**kwargs):

            group = None
            if request.user.groups.exists():
                group = request.user.groups.all()[0].name
                # print(group)
            if group in allowed_groups:
                return view_func(request,*args,**kwargs)
            else:
                return HttpResponse('Access Denied')

            # print(f'working: {allowed_groups}')
                
        return wrapper_func
    return allowed_user_dec