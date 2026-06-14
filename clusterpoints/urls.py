# clusterpoints/urls.py

from django.urls import path
from . import views

app_name = "clusterpoints"

urlpatterns = [

    # ===============================
    # KCSE Calculator
    # ===============================
    path(
        "calculator/",
        views.kcse_calculator_view,
        name="calculator"
    ),

    # ===============================
    # Export Cluster Results as PDF
    # ===============================
    path(
        "export/<int:result_id>/",
        views.export_cluster_pdf,
        name="export_cluster_pdf"
    ),

    # ===============================
    # Admin Analytics Dashboard
    # ===============================
    path(
        "admin-analytics/",
        views.admin_analytics,
        name="admin_analytics"
    ),

    # ===============================
    # Course Eligibility
    # ===============================
    path(
        "eligible/",
        views.eligible_courses_view,
        name="eligible_courses"
    ),

]