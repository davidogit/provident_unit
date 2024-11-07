from typing import Any
from django.urls import reverse
from django.views.generic import ListView,CreateView,DeleteView,UpdateView
from MultiScheme.models import InvestmentScheme
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
# Custom Decorators

from Member.decorators import tenant_required
from Admin.decorators import role_required


from rest_framework.generics import ListAPIView,RetrieveAPIView
from rest_framework.views import APIView
from .models import Tenant
from .serializers import TenantSerializer
from rest_framework.response import Response
from rest_framework import status


# Scheme List View
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Manager']), name='dispatch')
class SchemeList(ListView):
    template_name ='multischeme/scheme_list.html'
    model = InvestmentScheme
    paginate_by=10

    def get_queryset(self):
        tenant = self.request.tenant
        
        # Filter Schemes based on tenant
        if tenant:
            return InvestmentScheme.objects.filter(tenant=tenant)
        else:
            return InvestmentScheme.objects.none()


@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Manager']), name='dispatch')
class AddScheme(CreateView):
    template_name = 'multischeme/add_scheme.html'
    model = InvestmentScheme
    fields = ('name','administrative_costs_percentage','distribution_percentage','eligibility_criteria_months','payout_frequency','description')

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        tenant= self.request.tenant

        if tenant:
            context['frequency'] = InvestmentScheme.frequency
            context['payout_frequency'] = InvestmentScheme.choices
            context['options'] = InvestmentScheme.options
        else:
            context['frequency'] = []
            context['payout_frequency'] = []
            context['options'] = []

        return context
    
    # Assign tenant before saving
    def form_valid(self, form):
        tenant = self.request.tenant
        if tenant:
            form.instance.tenant = tenant
        return super().form_valid(form)
    
    # reverse url after a succesful save
    def get_success_url(self):
        tenant = self.request.tenant

        return reverse('scheme_list', kwargs={'tenant_id':tenant.id})

# API list view
class TenantApiListView(ListAPIView):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer

    def post(self,request,**kwargs):
        serializer = TenantSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data,status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)


# API detail view
class TenantApiPatchView(RetrieveAPIView):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer

    def patch(self,request,pk,**kwargs):
        # Retrieve instance to be patched
        try:
            obj = Tenant.objects.get(id=pk)
        except Tenant.DoesNotExist:
            return Response({'error':'Object not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = TenantSerializer(obj,data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        

