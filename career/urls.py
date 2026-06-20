from django.urls import path
from . import views

app_name = "career"

urlpatterns = [
    # Home / pathway selection
    path("", views.home, name="home"),

    # KCSE input page
    path("kcse-input/", views.kcse_input, name="kcse_input"),

    # Course detail view
    path("course/<int:match_id>/", views.course_detail, name="course_detail"),

    # Filter matches page
    path("filter-matches/", views.filter_matches, name="filter_matches"),

    # AI recommendations history
    path("ai-recommendations/", views.ai_recommendations, name="ai_recommendations"),

    # AJAX endpoints
    path("ajax/validate-tvet-subjects/", views.ajax_validate_tvet_subjects, name="ajax_validate_tvet_subjects"),
    path("ajax/update-admission/", views.ajax_update_admission, name="ajax_update_admission"),

    # Search courses
    path("search-courses/", views.search_courses, name="search_courses"),

    # Export matches
    path("export-matches/", views.export_matches_csv, name="export_matches"),

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

    # ── Session management ───────────────────────────
    path("clear/", views.clear_session, name="clear_session"),

    # ── Share results ────────────────────────────────
    path("share/create/",         views.share_result_create, name="share_result_create"),
    path("share/<uuid:token>/",   views.shared_result_view,  name="shared_result"),
]