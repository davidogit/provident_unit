"""
URL configuration for ProvidentFund project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static



from Member import views
from Fund import views as v
from django.contrib.auth import views as auth_views
from debug_toolbar.toolbar import debug_toolbar_urls

urlpatterns = [
    path('admin/', admin.site.urls),
    path('<str:tenant_id>/login/', views.loginView, name='login'),
    # path('<str:tenant_id>/', v.Invest.as_view(),),
    path('<str:tenant_id>/fund/', include('Fund.urls')),
    path('<str:tenant_id>/contributions/', include('contributions.urls')),
    path('<str:tenant_id>/members/', include('Member.urls')),
    path('<str:tenant_id>/pfund_admin/', include('Admin.urls')),
    path('<str:tenant_id>/schemes/', include('MultiScheme.urls')),

    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='reset_password.html'), name='password_reset'),
    path('password_reset_done/', auth_views.PasswordResetDoneView.as_view(template_name='reset_password_link_sent.html'), name='password_reset_done'),
    path('password_reset_confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='reset_password_details.html'), name='password_reset_confirm'),
    path('password_reset_complete/', auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_successful.html'), name='password_reset_complete'),
] + debug_toolbar_urls()

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

