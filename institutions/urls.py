from django.urls import path
from . import views

app_name = 'institutions'

urlpatterns = [
    # List all institution types
    path('', views.institution_types_list, name='institution_types_list'),

    # List institutions under a specific type
    path('<slug:type_slug>/', views.institution_type_detail, name='institution_type_detail'),

    # Institution detail page
    path('<slug:type_slug>/<slug:institution_slug>/', views.institution_detail, name='institution_detail'),
]