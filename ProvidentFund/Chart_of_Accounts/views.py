import json
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import TemplateView,DeleteView,UpdateView,View
from Chart_of_Accounts.models import ChartOfAccounts,AccountMapping,BankAccount
from MultiScheme.models import InvestmentScheme
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.db.models import Sum
# Create your views here.

class AddChartOfAccounts(TemplateView):
    template_name = 'add_chart_of_account.html'

    def post(self, request, *args, **kwargs):
        tenant = request.tenant
        user = request.user
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
                created_by=user,
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

# Update Chart of Accounts
class UpdateChartOfAccounts(UpdateView):
    model = ChartOfAccounts
    template_name = ''
    fields = ('parent','name','description','account_type','account_status','account_code')

    def get_object(self, queryset = ...):
        tenant = self.request.tenant
        account_id = self.kwargs.get('pk')
        print('START UPDATE')

        try:
            obj = ChartOfAccounts.objects.get(tenant=tenant,id=account_id)
        except Exception:
            return JsonResponse({
                'status':'error',
                'message': 'Account not found.'
            })
        return obj
    
    def form_valid(self, form):
        # Save the form instance
        self.object = form.save()


        # Return a JSON success response
        return JsonResponse({
            'status': 'success',
            'message': 'Account updated successfully.'
        })

    def form_invalid(self, form):
        # Return a JSON error response if the form is invalid
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to update account. Please check the input and try again. {form.errors}'
        })
    
    def get_success_url(self):
        tenant_id = self.request.tenant.id
        url = reverse('add_chart_of_account', kwargs={'tenant_id':tenant_id})
        return url


# Fetch Chart of Account Data
class FetchChartOfAccounts(View):
    def get(self,request,*args,**kwargs):
        if self.request.method == 'GET':
            print('START')
            tenant = self.request.tenant
            # account_code = self.request.GET.get('account_code')
            account_id = self.kwargs.get('pk')

            fields = [tenant,account_id]
            if not all(fields):
                return JsonResponse({
                    'status':'error',
                    'message':'Missing some fields'
                })
            
            # fetch account
            try:
                account = ChartOfAccounts.objects.get(tenant=tenant,id=account_id)
                print(account)
                return JsonResponse({
                    'status':'success',
                    'account':{
                        'id':account.id,
                        'name':account.name,
                        'account_code': account.account_code,
                        'description':account.description,
                        'account_status':account.account_status,
                        'account_type':account.account_type,
                        'parent':account.parent.id if account.parent else None
                    }
                })
            except Exception:
                return JsonResponse({
                    'status':'error',
                    'message':'Account not found'
                })



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

class AccountMappingView(TemplateView):
    template_name='account_mapping.html'

    def post(self,request, *args, **kwargs):
        if request.method == 'POST':
            tenant = request.tenant
            event_name = request.POST.get('event')
            scheme_id = request.POST.get('scheme_id')
            debit_code = request.POST.get('debit_id')
            credit_code = request.POST.get('credit_id')

            fields = [scheme_id,debit_code,credit_code,event_name]
            if not all(fields):
                return JsonResponse({
                    'status':'error',
                    'message':'some fields are missing'
                })
            
            # fetch debit and credit account
            debit_account = ChartOfAccounts.objects.get(tenant=tenant,account_code=debit_code)
            credit_account = ChartOfAccounts.objects.get(tenant=tenant,account_code=credit_code)
            scheme = InvestmentScheme.objects.get(tenant=tenant,id=scheme_id)

            try:
                AccountMapping.objects.create(
                    tenant=tenant,
                    scheme =scheme,
                    name = event_name,
                    debit_acc = debit_account,
                    credit_acc = credit_account,
                    created_by = self.request.user
                )
                return JsonResponse({
                    'status':'success',
                    'message':'Added successfully'
                })
            except IntegrityError as e:
                return JsonResponse({
                    'status':'error',
                    'message':f'Entry already exist'
                })
            except ValidationError as e:
                return JsonResponse({
                    'status':'error',
                    'message':f'{e}'
                })
            except Exception as e:
                return JsonResponse({
                    'status':'error',
                    'message':f'An error occured: {e}'
                })

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        context['actions']=AccountMapping.ACTIONS
        context['accounts'] = ChartOfAccounts.objects.filter(tenant=tenant)
        context['schemes'] = InvestmentScheme.objects.filter(tenant=tenant)
        context['mappings'] = AccountMapping.objects.filter(tenant=tenant)
        return context


# Delete View for Account Mapping
class AccountMappingDeleteView(DeleteView):
    model = AccountMapping
    template_name = ''

    def get_object(self, queryset = ...):
        tenant = self.request.tenant
        scheme_id = self.request.POST.get('scheme_id')
        mapping_id = self.request.POST.get('mapping_id')
        mapping_name = self.request.POST.get('mapping_name')

        fields = [tenant,scheme_id,mapping_id,mapping_name]
        if not all(fields):
            return JsonResponse({
                'status':'error',
                'message':'Missing some fields'
            })
        
        try:
            obj = AccountMapping.objects.get(tenant=tenant,scheme__id=scheme_id,id=mapping_id,name=mapping_name)
            return obj
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message':'Cannot find Mapping'
            })
        
    def get_success_url(self):
        tenant = self.request.tenant
        url = reverse('map_account', kwargs={'tenant_id':tenant.id})
        return url


# Update View for Account Mapping
class AccountMappingUpdateView(UpdateView):
    model = AccountMapping
    template_name = ''
    fields = ('__all__')

    def get_object(self, queryset = ...):
        tenant = self.request.tenant
        obj_id = self.request.POST.get('mapping_id')

        try:
            obj = AccountMapping.objects.get(
                tenant=tenant,
                id=obj_id
            )
        except AccountMapping.DoesNotExist:
            obj = AccountMapping.objects.none()

        return obj
    
    def form_valid(self, form):
        print('Form valid')
        tenant = self.request.tenant
        mapping_name = self.request.POST.get('name')
        scheme_id = self.request.POST.get('scheme')
        debit_code = self.request.POST.get('debit_acc')
        credit_code = self.request.POST.get('credit_acc')
        print(debit_code,credit_code)
        try:
            debit_acc = ChartOfAccounts.objects.get(
                tenant=tenant,
                id = debit_code
            )
            credit_acc = ChartOfAccounts.objects.get(
                tenant=tenant,
                id=credit_code
            )
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message':f'Could not find debit or credit account: {e}'
            })
        print('Form valid')
        try:
            scheme = InvestmentScheme.objects.get(
                tenant=tenant,
                id = scheme_id
            )
        except InvestmentScheme.DoesNotExist:
            return JsonResponse({
                'status':'error',
                'message':'Scheme not found'
            })
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message':f'An error occured {e}'
            })
        print('1')
        # Assigng scheme and mapping to form instance
        form.instance.tenant = tenant
        form.instance.name = mapping_name
        form.instance.scheme = scheme
        form.instance.debit_acc = debit_acc
        form.instance.credit_acc = credit_acc
        form.instance.created_by = self.request.user

        # save update
        self.object = form.save()
        return JsonResponse({
            'status':'success',
            'message':'Mapping updated successfully'
        })

    def form_invalid(self,form):
        debit_code = self.request.POST.get('debit_acc')
        credit_code = self.request.POST.get('credit_acc')

        print(debit_code,credit_code)

        print('Form invalid')
        return JsonResponse({
            'status':'error',
            'message':f'Invalid form submission. Error: {form.errors}'
        })
    
    def get_success_url(self):
        tenant_id = self.request.tenant.id
        url = reverse('map_account', kwargs={'tenant_id':tenant_id})
        return url

# ACCOUNT BALANCE QUERY
class AccountBalanceQuery(TemplateView):
    template_name = 'account_balance.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant
        natural_accounts_set = ChartOfAccounts.objects.filter(tenant=tenant,parent=None)
        child_accounts = ChartOfAccounts.objects.filter(tenant=tenant).exclude(parent=None)
        
        natural_accounts=[]
        other_accounts = []
        for account in natural_accounts_set:
            natural_accounts.append(
                {
                    'account':account,
                    'account_balance':account.calculate_total_balance()
                }
            )


        for other in child_accounts:
            other_accounts.append(
                {
                    'account':other,
                    'account_balance':other.calculate_total_balance()
                }
                )

        context['natural_accounts'] = natural_accounts
        context['child_accounts'] = other_accounts

        return context



# BANK ACCOUNT CREATION AND LIST
class BankAccountsView(TemplateView):
    template_name = 'bank_accounts.html'

    def post(self,request,*args,**kwargs):
        tenant = self.request.tenant
        account_number = self.request.POST.get('account_number')
        bank_name = self.request.POST.get('bank_name')
        account_holder_name = self.request.POST.get('account_holder_name')
        branch = self.request.POST.get('branch')
        account_type = self.request.POST.get('account_type')
        parent_Account_id = self.request.POST.get('parent_Account')
        currency = self.request.POST.get('currency')
        bank_email = self.request.POST.get('bank_email')


        all_fields = [tenant,account_holder_name,account_number,account_type,branch,bank_name,parent_Account_id,currency,bank_email]

        if not all(all_fields):
            return JsonResponse({
                'status':'error',
                'message':'some required fields are missing.'
            })
        
        # Get parent Account
        try:
            parent_account = ChartOfAccounts.objects.get(tenant=tenant,id=parent_Account_id)
        except Exception:
            return JsonResponse({
                'status':'error',
                'message':'Parent account not found.'
            })
        
        # create bank account
        try:
            BankAccount.objects.create(
                tenant=tenant,
                account_number=account_number,
                bank_name=bank_name,
                account_holder_name=account_holder_name,
                branch=branch,
                account_type=account_type,
                parent_Account=parent_account,
                currency=currency,
                bank_email = bank_email
            )
        except Exception:
            return JsonResponse({
                'status':'error',
                'message':'A bank with same account number already exists.'
            })
        
        return JsonResponse({
            'status':'success',
            'message':'Bank added successfully.'
        })


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.tenant

        if tenant:
            # fetch all bank accounts of tenant
            bank_accounts = BankAccount.objects.filter(
                tenant =tenant
            )
            # fetch parent accounts
            parent_accounts = ChartOfAccounts.objects.filter(
                tenant = tenant,
            ).exclude(parent=None)

            context['bank_accounts'] = bank_accounts
            context['parent_accounts'] = parent_accounts
            context['account_types'] = BankAccount.ACCOUNT_TYPE
            context['currency'] = BankAccount.CURRENCY

        return context

class DeleteBankView(DeleteView):
    model = BankAccount

    def get_object(self, queryset = ...):
        tenant = self.request.tenant
        obj_id = self.request.POST.get('bank_id')
        print('Start Deletion')
        all_fields = [tenant,obj_id]
        if not all(all_fields):
            return JsonResponse({
                'status':'error',
                'message':'Missing required fields.'
            })
        
        try:
            obj = BankAccount.objects.get(tenant=tenant,id=obj_id)
        except Exception:
            return JsonResponse({
                'status':'error',
                'message':'Bank not found.'
            })
        
        return obj

    def delete(self, request, *args, **kwargs):

        try: 
            self.object = self.get_object()
            self.object.delete()

            return JsonResponse({
                'status':'success',
                'message':'Bank deleted successfully.'
            })
        except BankAccount.DoesNotExist:
            return JsonResponse({
                'status':'error',
                'message':'Bank does not exist.'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status':'error',
                'message': f'An error occured: {str(e)}'
            },status=500)
        

    def get_success_url(self):
        tenant_id = self.request.tenant.id
        url = reverse('bank_accounts', kwargs={
            'tenant_id':tenant_id
        })
        return url


# Update View for Bank Account
class BankUpdateView(UpdateView):
    model = BankAccount
    template_engine = ''
    fields = (
        'account_number',
        'bank_name',
        'account_holder_name',
        'branch',
        'account_type',
        'parent_Account',
        'currency',
        'bank_email'
    )

    def get_object(self, queryset = ...):
        tenant = self.request.tenant
        bank_id = self.kwargs['pk']

        all_fields = [tenant,bank_id]
        if not all(all_fields):
            return JsonResponse({
                'status':'error',
                'message':'Missing required parameters'
            })
        
        if tenant:
            try:
                obj = BankAccount.objects.get(
                    tenant=tenant,
                    id = bank_id
                )
            except BankAccount.DoesNotExist:
                return JsonResponse({
                    'status':'error',
                    'message':'Bank does not exist'
                })
        else:
            return JsonResponse({
                'status':'error',
                'message':'Invalid tenant or bank ID'
            })

        return obj
    
    def form_valid(self, form):
        
        try:
            form.save()
            return JsonResponse({
                'status':'success',
                'message':'Update successful.'
            })
        except Exception:
            return JsonResponse({
                'status':'error',
                'message':'Error updating bank details'
            })
    
    def form_invalid(self, form):
        return JsonResponse({
            'status':'error',
            'message':f'An error occured: {str(form.errors)}'
        })
    
    def get(self, request, *args, **kwargs):
        tenant_id = request.tenant.id
        url = reverse('bank_accounts', kwargs={'tenant_id':tenant_id})
        return url


# Fetch bank detail for update template
class FetchBankDetail(TemplateView):
    def get(self, request, *args, **kwargs):
        tenant = request.tenant
        bank_id = kwargs['pk']

        all_fields = [tenant,bank_id]
        if not all(all_fields):
            return JsonResponse({
                'status':'error',
                'message':'Missing required parameters for fetch.'
            })
        
        try:
            bank = BankAccount.objects.get(
                tenant=tenant,
                id=bank_id
            )

            return JsonResponse({
                'status':'success',
                'bank':{
                    'id':bank.id,
                    'bank_name':bank.bank_name,
                    'account_number':bank.account_number,
                    'account_holder_name':bank.account_holder_name,
                    'account_type':bank.account_type,
                    'currency':bank.currency,
                    'branch':bank.branch,
                    'parent':bank.parent_Account.id if bank.parent_Account else None,
                    'bank_email': bank.bank_email
                }
            })
        except BankAccount.DoesNotExist:
            return JsonResponse({
                'status':'error',
                'message':'Bank account not found.'
            })