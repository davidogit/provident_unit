from typing import Any
from django.forms import BaseModelForm
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import ListView,CreateView,DeleteView,UpdateView
from MultiScheme.models import InvestmentScheme,SchemeSettings
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
# Custom Decorators

from Member.decorators import tenant_required
from Admin.decorators import role_required


from rest_framework.generics import ListAPIView,RetrieveAPIView
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
    fields = ('name','administrative_costs_percentage','distribution_percentage','eligibility_criteria_months','description')

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        tenant= self.request.tenant

        if tenant:
            # context['frequency'] = InvestmentScheme.frequency
            # context['payout_frequency'] = InvestmentScheme.choices
            context['options'] = InvestmentScheme.options
        else:
            # context['frequency'] = []
            # context['payout_frequency'] = []
            context['options'] = []

        return context
    
    # Assign tenant before saving
    def form_valid(self, form):
        tenant = self.request.tenant
        if tenant:
            form.instance.tenant = tenant
            instance = form.save()
            message = 'scheme created successfully, proceed to settings'

            # Create associated setting obj
            SchemeSettings.objects.create(
                investment_scheme = instance,
            )

            redirect_url = reverse('scheme_settings', kwargs={
                'tenant_id':tenant.id,
                'scheme_name':instance.id
            })
            return JsonResponse({'status':'success',
                                  'message':message, 'scheme_id':instance.id, 'redirect_url':redirect_url})
        else:
            return JsonResponse({'status':'error',
                                  'message':'An error occured'})
    
    def form_invalid(self, form):
        return JsonResponse({'status':'error',
                             'message':'An error occured'})



# Scheme Settings/Configuration
class SchemeSettingsView(CreateView):
    model = SchemeSettings
    fields = ('contribution_day','grace_period_contribution','delayed_interest_rate','period_of_delayed_calculation') #include all fields from model
    template_name = 'multischeme/scheme_settings.html'

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        scheme_id = self.request.scheme_name

        # get scheme object
        scheme = InvestmentScheme.objects.filter(id=scheme_id,tenant=tenant).prefetch_related('scheme_settings').first()
        # Try to get settings object
        try:
            settings = scheme.scheme_settings
            context['settings'] = settings
        except SchemeSettings.DoesNotExist:
            context['settings'] = SchemeSettings.objects.none()
        return context

    # Return invalid form response using Json
    def form_invalid(self, form: BaseModelForm) -> HttpResponse:
        print(f'Error: {form.errors}')
        return JsonResponse({'status':'error',
                              'message':'An error occured'})

    def form_valid(self, form: BaseModelForm) -> HttpResponse:
        # Get scheme and tenant
        tenant = self.request.tenant
        scheme_id = self.request.scheme_name

        scheme = InvestmentScheme.objects.filter(id=scheme_id,tenant=tenant).prefetch_related('scheme_settings').first()

        try:
            # get settings data from prefetched data
            settings = scheme.scheme_settings

            if not settings:
                return JsonResponse({'status':'error','message':'No settings file was found'})
            # Update fields
            for field in form.cleaned_data:
                setattr(settings,field,form.cleaned_data[field])
            settings.save()
            print('Saved successfully')
            redirect_url = reverse('scheme_settings', kwargs={'tenant_id' : tenant.id, 'scheme_name':scheme_id})
            return JsonResponse({'status':'success',
                                  'message':'Settings updated successfully.',
                                  'redirect_url':redirect_url})
        except Exception as e:
            return JsonResponse({'status':'error',
                                  'message':f'An error occured: {e}'})

        
        # return HttpResponseRedirect(self.get_success_url())
    
    # After successful creation redirect to scheme list page
    def get_success_url(self):
        tenant =  self.request.tenant
        scheme_id = self.request.scheme_name
        return reverse('scheme_settings', kwargs={'tenant_id' : tenant.id, 'scheme_name':scheme_id})


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
        

