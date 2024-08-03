from django.utils.deprecation import MiddlewareMixin
from MultiScheme.models import Tenant
import uuid

# middleware to retrieve Tenant ID

class URLTenantMiddleware(MiddlewareMixin):
    def process_request(self, request):
        path_parts = request.path.split('/')
        # Ensure admin is not affected by tenant_id
        if 'favicon.ico' not in path_parts:
            if 'admin' not in path_parts:

                if len(path_parts)>1:
                    # Get Tenant from url
                    tenant_id = path_parts[1]

                    request.tenant_id = (Tenant.objects.get(id=tenant_id)).id
                    # Get Scheme name from url
                    if len(path_parts)>3:
                        if not path_parts[3] =='':
                            scheme_name = int(path_parts[3])
                            request.scheme_name = scheme_name
                        else:
                            request.scheme_name = None
                    else:
                        request.scheme_name = None
                    try:
                        request.tenant = Tenant.objects.get(id=tenant_id)
                        

                    except Tenant.DoesNotExist:
                        request.tenant = None


  
                else:
                    request.tenant = None
                    request.scheme_name = None
            else:
                request.tenant = None
                request.scheme_name = None
        else:
            request.tenant = None
            request.scheme_name = None


