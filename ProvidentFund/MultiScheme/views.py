from typing import Any
from django.db.models.query import QuerySet
from django.forms import BaseModelForm
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import ListView,CreateView,DeleteView,UpdateView
from MultiScheme.models import InvestmentScheme
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
# Custom Decorators

from Member.decorators import tenant_required
from Admin.decorators import role_required



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
    fields = ('name','contribution_frequency','distribution_frequency','distribution_percentage','eligibility_criteria_months','payout_frequency','description')

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