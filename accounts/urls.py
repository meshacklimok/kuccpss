from django.urls import path, include
from . import views

app_name = "accounts"

urlpatterns = [
    # ==============================
    # Authentication (Custom Views)
    # ==============================
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.RegisterView.as_view(), name="register"),

    # Email verification
    path("verify-email/<str:token>/", views.email_verify_view, name="email_verify"),

    # Password change & re-authentication
    path("change-password/", views.change_password_view, name="change_password"),
    path("re-auth/", views.re_auth_view, name="re_auth"),

    # Dashboard / Profile
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("profile/", views.profile_update_view, name="profile"),

    # Saved courses & careers
    path("saved-courses/", views.saved_courses_view, name="saved_courses"),
    path("save-course/<int:course_id>/", views.toggle_save_course, name="toggle_save_course"),
    path("save-career/<int:profile_id>/", views.toggle_save_career, name="toggle_save_career"),

    # Course Shortlist / Compare
    path("shortlist/", views.shortlist_view, name="shortlist"),
    path("shortlist/toggle/<int:course_id>/", views.shortlist_toggle, name="shortlist_toggle"),
    path("shortlist/notes/<int:course_id>/", views.shortlist_update_notes, name="shortlist_notes"),
    path("shortlist/rank/<int:course_id>/", views.shortlist_set_rank, name="shortlist_rank"),
    path("shortlist/export/pdf/", views.export_shortlist_pdf, name="shortlist_pdf"),

    # Notifications
    path("notifications/", views.notifications_view, name="notifications"),
    path("notifications/mark-read/", views.mark_notifications_read, name="mark_notifications_read"),
    path("notifications/<int:notif_id>/read/", views.mark_notification_read, name="mark_notification_read"),
    path("notifications/broadcast/", views.broadcast_notification_view, name="broadcast_notification"),
    path("push/subscribe/",          views.push_subscribe,              name="push_subscribe"),

    # ==============================
    # Allauth URLs (Google OAuth + built-in email/password)
    # ==============================
    path("", include("allauth.urls")),
    path("terms/", views.terms_view, name="terms"),
    path("about/", views.about_view, name="about"),
    path("privacy/", views.privacy_view, name="privacy"),
    path("faq/", views.faq_view, name="faq"),

    # Referral system
    path("referral/",                    views.referral_view,            name="referral"),

    # Application tracker
    path("applications/",                views.applications_view,        name="applications"),
    path("applications/add/",            views.application_add_view,     name="application_add"),
    path("applications/<int:pk>/edit/",  views.application_update_view,  name="application_update"),
    path("applications/<int:pk>/delete/",views.application_delete_view,  name="application_delete"),
]