# dashboard/context_processors.py
from .models import InvestmentScheme

def schemes_processor(request):
    tenant = getattr(request, 'tenant', None)
    schemes = InvestmentScheme.objects.filter(tenant=tenant) if tenant else []
    return {
        'schemes': schemes
    }