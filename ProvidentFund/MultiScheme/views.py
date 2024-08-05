# from typing import Any
# from django.db.models.query import QuerySet
# from django.shortcuts import render
# from .models import InvestmentScheme
# from django.views.generic import ListView
# # Create your views here.

# # View to group schemes
# class Base(ListView):
#     template_name = 'dashboard/base.html'
#     model = InvestmentScheme

#     def get_queryset(self):

#         # Get tenant from middleware
#         tenant = self.request.tenant

#         if tenant:
#             return InvestmentScheme.objects.filter(tenant = tenant)
#         else:
#             return InvestmentScheme.objects.none()
        
#     def get_context_data(self, **kwargs: Any):
#         context = super().get_context_data(**kwargs)

#         # Get filtered list for a specific tenant
#         queryset = self.get_queryset()

#         context['schemes'] = queryset

#         return context