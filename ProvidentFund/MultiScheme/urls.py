from django.urls import path
from MultiScheme import views

urlpatterns = [
    path('scheme_list/', views.SchemeList.as_view(), name='scheme_list'),
    path('add_scheme/', views.AddScheme.as_view(), name='add_scheme'),
    path('<int:scheme_name>/scheme_settings/', views.SchemeSettingsView.as_view(), name='scheme_settings'),

    #TENANT API URLS
    # POST
    path('tenant_api_post/', views.TenantApiListView.as_view(), name='tenant_api_post'),

    # PATCH
    path('tenant_api_patch/<int:pk>/', views.TenantApiPatchView.as_view(), name='tanant_api_patch'),

]