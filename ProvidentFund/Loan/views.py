from django.shortcuts import render
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.views.generic import ListView,CreateView
from .models import LoanApplication
from .forms import LoanForm
from django.utils.decorators import method_decorator
from Member.decorators import tenant_login_required,tenant_required
from Admin.decorators import role_required

# Create your views here.

@method_decorator(tenant_login_required, name="dispatch")
@method_decorator(tenant_required, name='dispatch')
@method_decorator(role_required(role=[
    'Treasury Manager','Treasury Analyst','Treasury Supervisor','Scheme Manager','Scheme Analyst','Scheme Supervisor','Contributions Manager','Contributions Analyst','Contributions Supervisor','Finance Manager','Finance Analyst','Finance Supervisor'
]), name='dispatch')
class LoanApplicationView(CreateView):
    template_name = 'loan_application.html'
    model = LoanApplication
    form_class = LoanForm

    def form_valid(self, form):
        tenant = getattr(self.request, 'tenant', None)
        member = getattr(self.request.user, 'member', None)

        if tenant and member:
            form.instance.tenant = tenant
            form.instance.member = member
            return super().form_valid(form)
        else:
            return JsonResponse(
                {"error": "Missing tenant or member"},
                status=400
            )

    def get_success_url(self):
        return reverse_lazy('loan_application_success')


class LoanApprovalView(ListView):
    model = LoanApplication
    template_name = 'loan_approval.html'

