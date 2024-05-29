from django.urls import path
from . import views


urlpatterns =[
    path('', views.Invest.as_view(), name='finance_page'),
    path('ContributionsList/', views.ContributionsListView.as_view(), name='contributions_list'),
    path('ContributionsList2/', views.ContributionsListView2.as_view(), name='contributions_listpf2'),
    path('ContributionsDetails/<int:pk>/', views.ContributionsDetailView.as_view(), name='contributions_details'),
]