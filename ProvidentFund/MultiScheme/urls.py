from django.urls import path
from MultiScheme import views

urlpatterns = [
    path('scheme_list/', views.SchemeList.as_view(), name='scheme_list'),
    path('add_scheme/', views.AddScheme.as_view(), name='add_scheme'),
]