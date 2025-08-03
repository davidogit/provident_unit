from django.http import JsonResponse
import logging
from django.views.generic import TemplateView,ListView,CreateView,UpdateView,DeleteView,View

from .forms import ApprovalWorkflowForm, WorkflowStepForm
from .models import ApprovalActionType, RoleType, ApprovalWorkflow, WorkflowStep


# Create your views here.
logger = logging.getLogger(__name__)

class WorkFlowView(ListView):
    template_name = 'approval_workflow_admin.html'
    model = ApprovalWorkflow
    paginate_by = 20
    context_object_name = 'workflows'

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return self.model.objects.none()
        return self.model.objects.prefetch_related('steps').filter(tenant=tenant)


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)

        if not tenant:
            return None

        context.update({
            'role_types': RoleType.choices,
            'action_types': ApprovalActionType.choices
        })

        return context


class HandleWorkFlowCreation(View):
    model = ApprovalWorkflow
    form_class1 = ApprovalWorkflowForm
    form_class2 = WorkflowStepForm

    def post(self, request, *args, **kwargs):
        tenant = getattr(self.request, 'tenant', None)
        data = request.POST

        if not tenant:
            return JsonResponse({
                'status':'error',
                'message':'Invalid request.'
            },status=400)

        if not data:
            return JsonResponse({
                'status':'error',
                'message':'No data provided.'
            },status=400)

        try:
            workflow_form = self.form_class1(data)
            if workflow_form.is_valid():
                workflow = ApprovalWorkflow.objects.create(
                    tenant=tenant,
                    name=workflow_form.cleaned_data['name'],
                    action_type=workflow_form.cleaned_data['action_type'],
                    is_active=workflow_form.cleaned_data['is_active']
                )
                print(f'Workflow: {workflow}')

                print(f'Data: {data}')
                #   Extract steps from request
                steps = []
                for key in data:
                    print(f'key: {key} value: {data.get(key)}')
                    if key.startswith('steps[') and key.endswith('][order]'):
                        print('key starts with steps')
                        index = key.split('[')[1].split(']')[0]
                        print(f'index: {index}')
                        step = {
                            'order': int(data.get(f'steps[{index}][order]')),
                            'role': data.get(f'steps[{index}][role]'),
                            'required_approvals': int(data.get(f'steps[{index}][required_approvals]')),
                        }
                        print(f'Individual Step: {step}')
                        step_form = self.form_class2(step)
                        if step_form.is_valid():
                            steps.append(step)
                        else:
                            return JsonResponse({
                                'status':'error',
                                'message':f'Error creating workflow step: check the form and try again. {step_form.errors}'
                            })

                print(f'Steps: {steps}')
                #   Create steps
                for step in steps:
                    WorkflowStep.objects.create(
                        workflow=workflow,
                        order=step['order'],
                        role=step['role'],
                        required_approvals=step['required_approvals']
                    )

                return  JsonResponse({
                    'status':'success',
                    'message':'Workflow created successfully.'
                })

            else:
                return JsonResponse({
                    'status':'error',
                    'message':f'Error creating workflow. Please check the form and try again. {workflow_form.errors}'
                },status=400)
        except Exception as e:
            logger.error(f'Error creating workflow: {e}')
            return JsonResponse({
                'status': 'error',
                'message': f'Internal Server error.'
            },status=500)
