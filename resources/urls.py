from django.urls import path
from . import views

app_name = "resources"

urlpatterns = [
    path("", views.resource_list, name="resource_list"),
    path("articles/", views.article_list, name="article_list"),
    path("articles/<slug:slug>/", views.article_detail, name="article_detail"),
    path("<slug:slug>/", views.resource_detail, name="resource_detail"),
]
