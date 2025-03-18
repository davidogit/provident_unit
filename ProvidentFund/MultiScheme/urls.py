from django.urls import path
from MultiScheme import views

urlpatterns = [
    path('scheme_list/', views.SchemeList.as_view(), name='scheme_list'),
    path('add_scheme/', views.CreateScheme.as_view(), name='add_scheme'),
    path('scheme_settings/<int:pk>/', views.SchemeSettingsView.as_view(), name='scheme_settings'),
    path('scheme_approval/', views.SchemeApproval.as_view(), name='scheme_approval'),

    #TENANT API URLS
    # POST
    path('tenant_api_post/', views.TenantApiListView.as_view(), name='tenant_api_post'),

    # PATCH
    path('tenant_api_patch/<int:pk>/', views.TenantApiPatchView.as_view(), name='tanant_api_patch'),

]