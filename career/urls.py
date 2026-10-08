from django.urls import path
from . import views

app_name = "career"

urlpatterns = [
    # Home / pathway selection
    path("", views.home, name="home"),

    # Retired KCSE-input flow (legacy career.Course tables) → 301 to the engine
    path("kcse-input/", views.legacy_redirect, name="kcse_input"),
    path("course/<int:match_id>/", views.legacy_redirect, name="course_detail"),
    path("filter-matches/", views.legacy_redirect, name="filter_matches"),
    path("ai-recommendations/", views.legacy_redirect, name="ai_recommendations"),
    path("search-courses/", views.legacy_redirect, name="search_courses"),
    path("export-matches/", views.legacy_redirect, name="export_matches"),

    # Career profiles
    path("profiles/", views.career_profiles_list, name="career_profiles"),
    path("profiles/<slug:slug>/", views.career_profile_detail, name="career_profile_detail"),

    # Career assessment quiz
    path("quiz/", views.quiz_view, name="quiz"),
    path("quiz/results/", views.quiz_results_view, name="quiz_results"),

    # ── Degree flow ──────────────────────────────────
    path("degree/", views.degree_entry, name="degree_entry"),
    path("degree/calculate/", views.degree_calculate, name="degree_calculate"),
    path("degree/options/", views.degree_options, name="degree_options"),
    path("degree/upload/", views.degree_upload, name="degree_upload"),
    path("degree/paste/", views.degree_paste, name="degree_paste"),
    path("degree/manual/", views.degree_manual, name="degree_manual"),

    # ── Other pathway inputs ─────────────────────────
    path("input/<str:pathway>/", views.pathway_input, name="pathway_input"),

    # ── Loading & Results ────────────────────────────
    path("loading/<str:pathway>/", views.loading_page, name="loading_page"),
    path("results/", views.career_results, name="career_results"),

    # ── PDF Downloads ────────────────────────────────
    path("results/pdf/quick/",  views.career_results_pdf_quick,   name="pdf_quick"),
    path("results/pdf/report/", views.career_results_pdf_detailed, name="pdf_report"),

    # ── AI Insight (AJAX) ────────────────────────────
    path("ajax/ai-insight/", views.ajax_ai_insight, name="ajax_ai_insight"),
    path("ajax/ai-chat/",    views.ajax_ai_chat,    name="ajax_ai_chat"),

    # ── CareerNext AI Chat page ───────────────────────
    path("chat/", views.career_chat, name="career_chat"),

    # ── Submission lock ──────────────────────────────
    path("submission/confirm/",      views.confirm_submission, name="confirm_submission"),
    path("submission/recalculate/",  views.recalculate_view,   name="recalculate"),

    # ── Session management ───────────────────────────
    path("clear/", views.clear_session, name="clear_session"),

    # ── Share results ────────────────────────────────
    path("share/create/",         views.share_result_create, name="share_result_create"),
    path("share/<uuid:token>/",   views.shared_result_view,  name="shared_result"),
]