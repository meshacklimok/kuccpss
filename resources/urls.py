from django.urls import path
from . import views

app_name = "resources"

urlpatterns = [
    path("", views.resource_list, name="resource_list"),
    path("articles/", views.article_list, name="article_list"),
    path("articles/<slug:slug>/", views.article_detail, name="article_detail"),
    path("kuccps-calendar/", views.kuccps_calendar, name="kuccps_calendar"),
    path("how-to-guides/", views.how_to_guides, name="how_to_guides"),
    path("feedback/submit/", views.submit_feedback, name="submit_feedback"),
    path("<slug:slug>/", views.resource_detail, name="resource_detail"),
]
