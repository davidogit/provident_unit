from typing import Any
from django.db.models.query import QuerySet
from django.views.generic import TemplateView, ListView, DetailView
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from .models import StaffAPI, Contribution
import requests
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views import View
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect
from collections import defaultdict
from datetime import datetime
from django.shortcuts import redirect

# Create your views here.
@method_decorator(login_required,name = "dispatch")
class Invest(TemplateView):
    template_name='dashboard/finance.html'


@method_decorator(login_required,name = "dispatch")
class StaffMemberListView(ListView):
    model = StaffAPI
    template_name = 'contributions/staffmember_list.html'
    context_object_name = 'memberships'
    paginate_by = 5

    def get_queryset(self):
        return StaffAPI.objects.filter(ExitedFlag=False)

    
    @method_decorator(login_required, name="dispatch")
    def get(self, request, *args, **kwargs):
        response = requests.get('https://66718737e083e62ee43bf829.mockapi.io/api/v1/addmembership')
        memberships = response.json()

        for membership in memberships:
            ExitedFlag = membership.get('ExitedFlag', False)
            ExitedDate = membership.get('ExitedDate', None)
            if ExitedFlag and ExitedDate:
                ExitedDate = timezone.now() if not ExitedDate else ExitedDate
            else:
                ExitedDate = None
            api_id = membership.get('Id')
            staff_member, created = StaffAPI.objects.update_or_create(
                Id=api_id,
                defaults={
                    'Fullname': membership.get('Fullname', ''),
                    'Staffnumber': membership.get('Staffnumber', ''),
                    'Datejoined': membership.get('Datejoined', '1970-01-01'),
                    'status': membership.get('status', ''),
                    'Fundtype': membership.get('Fundtype', ''),
                    'EmployeeAmount': membership.get('EmployeeAmount', 0.0),
                    'EmployerAmount': membership.get('EmployerAmount', 0.0),
                    'RetroEmployeeAmount': membership.get('RetroEmployeeAmount', 0.0),
                    'RetroEmployerAmount': membership.get('RetroEmployerAmount', 0.0),
                    'Employee55Amount': membership.get('Employee55Amount', 0.0),
                    'Employer55Amount': membership.get('Employer55Amount', 0.0),
                    'RetroEmployee55Amount': membership.get('RetroEmployee55Amount', 0.0),
                    'RetroEmployer55Amount': membership.get('RetroEmployer55Amount', 0.0),
                    'ContributionDate': membership.get('ContributionDate', '1970-01-01'),
                    'ExitedDate': membership.get('ExitedDate', '1970-01-01'),
                    'ExitedFlag': membership.get('ExitedFlag', False),
                    'month': membership.get('month', '')
                 }
            )

            # Update the contribution details
            if 'contributions' in membership:
                for contrib in membership['contributions']:
                    Contribution.objects.update_or_create(
                        member=staff_member,
                        month=contrib['month'],
                        year=contrib['year'],
                        defaults={
                            'EmployeeAmount': contrib['EmployeeAmount'],
                            'EmployerAmount': contrib['EmployerAmount'],
                            'RetroEmployeeAmount': contrib['RetroEmployeeAmount'],
                            'RetroEmployerAmount': contrib['RetroEmployerAmount'],
                            'Employee55Amount': contrib['Employee55Amount'],
                            'Employer55Amount': contrib['Employer55Amount'],
                            'RetroEmployee55Amount': contrib['RetroEmployee55Amount'],
                            'RetroEmployer55Amount': contrib['RetroEmployer55Amount'],
                            'ContributionDate': contrib['ContributionDate'],
                        }
                    )
        return super().get(request, *args, **kwargs)
    

    
    
@method_decorator(login_required, name="dispatch")
class OptOutMemberView(View):
    def post(self, request, *args, **kwargs):
        member_id = kwargs.get('pk')
        member = get_object_or_404(StaffAPI, pk=member_id)
        member.ExitedDate = timezone.now()
        member.ExitedFlag = True
        member.save()
        return JsonResponse({'status': 'success'}, status=200)
    



@method_decorator(login_required, name='dispatch')
class StaffMemberDetailView(DetailView):
    model = StaffAPI
    template_name = 'contributions/staffmember_detail.html'
    context_object_name = 'membership'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_year = self.request.GET.get('year')
        
        years = list(range(2020, datetime.now().year + 1))
        context['years'] = years
        context['selected_year'] = int(selected_year) if selected_year else None

        if selected_year:
            contributions = Contribution.objects.filter(
                member=self.object,
                year=selected_year
            ).order_by('ContributionDate')

            monthly_contributions = defaultdict(list)
            for contribution in contributions:
                month_name = contribution.ContributionDate.strftime('%B')
                monthly_contributions[month_name].append(contribution)
            
            context['monthly_contributions'] = monthly_contributions

        return context

@method_decorator(login_required,name = "dispatch")
class Contributed(ListView):
    model = Contribution
    template_name = 'contributions/contributed.html'
    context_object_name = 'contributions'
    paginate_by = 10

    def get_queryset(self):
        user_id = self.kwargs.get('membership_id')
        return super().get_queryset().filter(member_id=user_id)
    
    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
        
    #     user_id = self.request.user.id
    #     # year = self.request.GET.get('year')
    #     context['user_contribution']= self.get_queryset()

    #     return context