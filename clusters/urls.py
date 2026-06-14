# clusters/urls.py
from django.urls import path
from . import views

app_name = 'clusters'

urlpatterns = [
    # List all clusters
    path('', views.cluster_list, name='cluster_list'),

    # Cluster detail page (slug for clean URL)
    path('<slug:slug>/', views.cluster_detail, name='cluster_detail'),

    # Optional: Front-end forms for creating/editing clusters
    path('create/', views.cluster_create, name='cluster_create'),
    path('<slug:slug>/edit/', views.cluster_edit, name='cluster_edit'),
]