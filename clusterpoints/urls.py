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
        "export/",
        views.export_cluster_pdf,
        name="export_cluster_pdf"
    ),

    # ===============================
    # Full Results PDF (scores + eligible courses)
    # ===============================
    path(
        "export/full/",
        views.export_full_results_pdf,
        name="export_full_results_pdf"
    ),

    # ===============================
    # Recalculate (reset grade lock)
    # ===============================
    path(
        "recalculate/",
        views.recalculate_view,
        name="recalculate"
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

    # ===============================
    # Share Calculator Results
    # ===============================
    path(
        "share/create/",
        views.share_calculator_create,
        name="share_calculator_create"
    ),

]