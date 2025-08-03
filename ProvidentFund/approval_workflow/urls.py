from django.urls import path

from approval_workflow import views

urlpatterns = [
    path('', views.WorkFlowView.as_view(), name='workflow_view'),
    path('create-workflow/',views.HandleWorkFlowCreation.as_view(), name='create_workflow')
]