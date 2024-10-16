from typing import Any
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from MultiScheme.models import Tenant
from django.http import HttpRequest
from django.urls import resolve
from threading import local

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
                    # print(request.tenant)
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

_user = local() # locally storing the request.user for every request that is made

class CurrentUserMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        _user.value = request.user
        response = self.get_response(request)

        return response

# Returns the current user when called
def get_current_user():
    return getattr(_user, 'value', None)