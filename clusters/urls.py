# clusters/urls.py
from django.urls import path
from . import views

app_name = 'clusters'

urlpatterns = [
    path('', views.cluster_list, name='cluster_list'),
    path('create/', views.cluster_create, name='cluster_create'),
    path('<slug:slug>/', views.cluster_detail, name='cluster_detail'),
    path('<slug:slug>/courses/', views.cluster_courses, name='cluster_courses'),
    path('<slug:slug>/edit/', views.cluster_edit, name='cluster_edit'),
    path('<slug:cluster_slug>/subject-groups/create/', views.subject_group_create, name='subject_group_create'),
    path('subject-groups/<int:group_id>/edit/', views.subject_group_edit, name='subject_group_edit'),
]