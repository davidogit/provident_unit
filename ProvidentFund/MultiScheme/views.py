from typing import Any

from django.db import transaction
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

from approval_workflow.approval_engine import ApprovalWorkflowEngine
from approval_workflow.models import ApprovalActionType
from .models import Tenant
from .serializers import TenantSerializer
from rest_framework.response import Response
from rest_framework import status
from .forms import SchemeCreationForm
import logging

logger = logging.getLogger(__name__)


# Scheme List View
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Scheme Manager','Scheme Supervisor','Scheme Analyst']), name='dispatch')
class SchemeList(ListView):
    template_name ='multischeme/scheme_list.html'
    model = InvestmentScheme
    paginate_by=10

    def get_queryset(self):
        tenant = getattr(self.request,'tenant',None)
        
        # Filter Schemes based on tenant
        if tenant:
            return self.model.objects.filter(
                tenant=tenant,
                approved=True
            )
        else:
            return self.model.objects.none()


@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Scheme Analyst']), name='dispatch')
class CreateScheme(CreateView):
    template_name = 'multischeme/add_scheme.html'
    model = InvestmentScheme
    form_class=SchemeCreationForm
    
    # Assign tenant before saving  
    def form_valid(self, form):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return JsonResponse({
                'status': 'error',
                'message': 'An error occurred'
            })

        with transaction.atomic():
            form.instance.tenant = tenant
            instance = form.save()
            message = 'scheme created successfully, proceed to settings'

            # Create the associated setting obj
            SchemeSettings.objects.create(
                investment_scheme = instance,
            )

            try:
                # Initiate approval workflow
                engine = ApprovalWorkflowEngine(
                    tenant=tenant,
                    target_object=instance,
                    action_type=ApprovalActionType.SCHEME_APPROVAL.value
                )

                engine.start_workflow()
            except ValueError as val_e:
                # Rollback scheme and settings creation
                transaction.set_rollback(True)
                return JsonResponse({
                    'status':'error',
                    'message':str(val_e)
                })
            except Exception as e:
                # Rollback changes
                transaction.set_rollback(True)
                logger.error(f'Error creating approval workflow: {e}')
                return JsonResponse({
                    'status':'error',
                    'message':"An error occurred"
                },status=500)

            redirect_url = reverse('scheme_settings', kwargs={
                'tenant_id':tenant.id,
                'pk':instance.id
            })
            return JsonResponse({
                'status':'success',
                'message':message, 'scheme_id':instance.id,
                'redirect_url':redirect_url #Redirects user to the settings page.
            })

    
    def form_invalid(self, form):
        return JsonResponse({
            'status':'error',
            'message':'An error occurred'
        })



# Scheme Settings/Configuration
@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Scheme Supervisor','Scheme Analyst']), name='dispatch')
class SchemeSettingsView(UpdateView):
    model = SchemeSettings
    fields = ('contribution_day','grace_period_contribution','delayed_interest_rate','period_of_delayed_calculation') #include all fields from model
    template_name = 'multischeme/scheme_settings.html'

    def get_object(self, queryset = ...):
        tenant= getattr(self.request, 'tenant', None)
        pk = self.kwargs.get('pk')
        return get_object_or_404(
            self.model,
            investment_scheme__tenant=tenant,
            investment_scheme__id=pk
        )

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        context['settings'] = self.object
        return context

    # Return invalid form response using JSON
    def form_invalid(self, form):
        print(f'Error: {form.errors}')
        return JsonResponse({
            'status':'error',
            'message':'An error occurred'
        })

    def form_valid(self, form):
        self.object = form.save()  # Save the form
        return JsonResponse({
            'status': 'success',
            'message': 'Settings updated successfully.',
            'redirect_url': self.get_success_url()
        })
    
    # After successful creation redirect to the scheme list page
    def get_success_url(self):
        tenant =  getattr(self.request, 'tenant', None)
        scheme_id = self.kwargs.get('pk')
        return reverse('scheme_settings', kwargs={'tenant_id' : tenant.id, 'pk':scheme_id})



@method_decorator(login_required, name='dispatch')
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=['Scheme Manager']), name='dispatch')
class SchemeApproval(ListView):
    model = InvestmentScheme
    template_name = 'multischeme/scheme_approval.html'
    paginate_by = 10
    context_object_name = 'scheme_list'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            # Filter only schemes with settings
            return self.model.objects.filter(
                tenant=tenant,
                approved=False
            ).exclude(scheme_settings=None).order_by('-created_date')
        else:
            return self.model.objects.none()

    
    def post(self,*args,**kwargs):
        tenant = getattr(self.request, 'tenant', None)
        user = getattr(self.request, 'user', None)
        scheme_id = self.request.POST.get('scheme_id')

        if not tenant or not user:
            return JsonResponse({
                'status':'error',
                'message':'Invalid request.'
            })

        if not scheme_id:
            return JsonResponse({
                'status':'error',
                'message':'No scheme id provided.'
            })

        scheme = self.model.objects.filter(
            id=scheme_id,
            tenant=tenant,
            approved=False
        ).first()

        if not scheme:
            return JsonResponse({
                'status': 'error',
                'message': 'Scheme does not exist.'
            })

        try:
            engine = ApprovalWorkflowEngine(
                tenant=tenant,
                target_object=scheme,
                action_type=ApprovalActionType.SCHEME_APPROVAL.value
            )

            approval_instance = engine.start_workflow()

            engine.approve(user=user,instance_id=approval_instance.id)
        except ValueError as val_e:
            return JsonResponse({
                'status':'error',
                'message':str(val_e)
            })
        except PermissionError as perm_e:
            return JsonResponse({
                'status':'error',
                'message':str(perm_e)
            })
        except Exception as e:
            logger.error(f'Error during Scheme approval workflow: {e}')
            return JsonResponse({
                'status':'error',
                'message':"An error occurred"
            })

        return JsonResponse({
            'status':'success',
            'message':'Scheme approved successfully.'
        })



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