import json
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.generic import CreateView,TemplateView,DeleteView
from Chart_of_Accounts.models import ChartOfAccounts
from Chart_of_Accounts.forms import ChartOfAccountsForm
from django.db.models import F
# Create your views here.

class AddChartOfAccounts(TemplateView):
    template_name = 'add_chart_of_account.html'

    def post(self, request, *args, **kwargs):
        tenant = request.tenant
        parent_id = request.POST.get('parent','')
        account_name = request.POST.get('name','')
        account_type = request.POST.get('account_type','')
        account_code = request.POST.get('account_code','')
        description = request.POST.get('description','')
        account_status = request.POST.get('account_status')
        
        fields = all([account_name,account_code,account_type,account_status])
        
        if not fields:
            return JsonResponse({
                'status':'error',
                'message':'Missing Fields'
            })
        
        # prevent duplicated account codes
        if account_code and ChartOfAccounts.objects.filter(tenant=tenant,account_code=account_code).exists():
            return JsonResponse({
                'status':'error',
                'message':'Account code already exist'
            })

        parent = None
        if parent_id:
            try:
                parent = ChartOfAccounts.objects.get(tenant=tenant,id=parent_id)
            except Exception:
                return JsonResponse({
                    'status':'error',
                    'message':'Parent Account does not exist'
                })
        # create chat of accounts
        try:
            ChartOfAccounts.objects.update_or_create(
                tenant=tenant,
                parent = parent,
                name=account_name,
                description=description,
                account_type=account_type,
                account_status=account_status,
                account_code=account_code,
            )
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message':f'Error occured: {e}'
            })

        return JsonResponse({
            'status':'success',
            'message':'Chart of account created successfully.'
        })
    
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        account_types = ChartOfAccounts.ACCOUNT_TYPES
        account_status = ChartOfAccounts.ACCOUNT_STATUS
        available_accounts = ChartOfAccounts.objects.filter(tenant=tenant)

        context['chart_of_accounts'] = available_accounts
        context['parent_accounts'] = available_accounts
        context['account_types'] = account_types
        context['account_status'] = account_status
        return context



class DeleteChartOfAccount(DeleteView):
    model= ChartOfAccounts
    template_name = 'add_chart_of_account.html'

    def get_object(self, queryset = ...):
        tenant = self.request.tenant
        chart_of_account_id = self.kwargs.get('pk')
        print(f'Delete Object with id {chart_of_account_id}')
        if tenant and chart_of_account_id:
            obj = get_object_or_404(ChartOfAccounts, tenant=tenant,id=chart_of_account_id)
            print(f'Object: {obj}')

        return obj
    
    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj:
            obj.delete()
            return JsonResponse({
                'status':'success',
                'message':'Deletion successful'
            })
        else:
            return JsonResponse({
                'status':'error',
                'message':'Could not delete selected account'
            })
    
    def get_success_url(self):
        tenant_id = self.request.tenant.id

        return reverse('add_chart_of_account', kwargs={'tenant_id':tenant_id})