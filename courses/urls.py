from django.urls import path
from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    # List all top-level course types
    path('', views.course_types_list, name='course_types_list'),

    # Detail for a course type: shows categories or courses
    path('<slug:type_slug>/', views.course_type_detail, name='course_type_detail'),

    # Detail for a category under a type
    path('<slug:type_slug>/<slug:category_slug>/', views.course_category_detail, name='course_category_detail'),

    # Course detail page
    path('<slug:type_slug>/<slug:category_slug>/<slug:course_slug>/', views.course_detail, name='course_detail'),

    # Optional: If some types have no category (e.g., KMTC), direct course detail
    path('<slug:type_slug>/<slug:course_slug>/', views.course_detail, name='course_detail_no_category'),
]