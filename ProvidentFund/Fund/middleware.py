from typing import Any
from django.conf import settings
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from MultiScheme.models import Tenant
from django.http import HttpRequest
from django.urls import resolve
import logging
logger = logging.getLogger(__name__)

class TenantLoginUrlMiddleware(MiddlewareMixin):
    def __init__(self,get_response):
        self.get_response = get_response

    def __call__(self,request):
        tenant_code = self.get_tenant_id(request)
        # Extract code from tenant
        print(tenant_code)

        # Generate dynamic login url path
        if tenant_code:
            request.login_url =f'/{tenant_code}/login/'
        else:
            # Default login url
            request.login_url = settings.LOGIN_URL
        
        response = self.get_response(request)
        return response
    
    def get_tenant_id(self,request: HttpRequest):
        path_parts = request.path.split('/')

        # Ensure admin is not affected by tenant_id
        if len(path_parts) > 1:
            try:
                tenant_id = int(path_parts[1])
                return tenant_id
            except(IndexError, ValueError):
                return None
        else:
            return None




# middleware to retrieve Tenant ID
class URLTenantMiddleware(MiddlewareMixin):
    def process_request(self, request: HttpRequest):
        path_parts = request.path.split('/')

        # Ensure admin is not affected by tenant_id
        if len(path_parts) > 1:
            try:
                tenant_id = int(path_parts[1])
                try:
                    request.tenant = Tenant.objects.get(id=tenant_id)

                except Tenant.DoesNotExist:
                    request.tenant = None
            except ValueError:
                request.tenant = None
        else:
            request.tenant = None

        # Get Scheme name from url
        if len(path_parts) > 3:
            try:
                scheme_name = int(path_parts[3])
                request.scheme_name = scheme_name
            except ValueError:
                request.scheme_name = None
        else:
            request.scheme_name = None



# Middleware for Trackin Pages users visit
class PageVisitLoggingMiddleware(MiddlewareMixin):
    def __init__(self,get_response):
        self.get_response = get_response
    
    def __call__(self, request:HttpRequest):
        # Import task
        from .tasks import track_page_visits
        response = self.get_response(request)

        if request.user.is_authenticated and request.method == 'GET':
            # get view and url
            path = request.path
            view_name = resolve(request.path_info).url_name
            user_ip = self.get_client_ip(request)
            user_id = request.user.pk
            # print(user_id)
            
            split = path.split('/')[1]

            value = self.is_member(view_name)
            if value and split != 'admin': #Excludes all requests made from the django Admin page
                track_page_visits.delay(str(user_id),path,view_name,user_ip) #calls task to create AuditTrail
                    
            
        return response
    
    # checks to exclude static files and other page elements that loads upon request
    def is_member(self, value):
        iterable=['jsi18n','Fund_audittrail_change',None,'Fund_audittrail_changelist']
        for item in iterable:
            if value is item or value == item:
                return False
        return True
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
            
        


# Middleware to extract user from request and pass to signals since signals do not have access to HTTP response

from threading import local

_threads_local = local() # locally storing the request.user for every request that is made

# Returns the current user when called
def get_current_user():
    return getattr(_threads_local,'user', None)



class CurrentUserMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        _threads_local.user = getattr(request, 'user' , None)
        response = self.get_response(request)
        print(f'Username: {_threads_local.user}')
    
        return response