from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from MultiScheme.models import Tenant
from django.http import HttpRequest

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



# class TenantLoginMiddleware(MiddlewareMixin):
#     def process_request(self,request):
#         if not request.user.is_authenticated:
#             tenant = request.tenant
#             if tenant:
#                 login_url = f'/{tenant.id}/login'
#                 return redirect(login_url)
