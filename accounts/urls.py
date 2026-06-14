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

    # Password change (logged in)
    path("change-password/", views.change_password_view, name="change_password"),

    # Dashboard / Profile
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("profile/", views.profile_update_view, name="profile"),

    # Saved courses & careers
    path("saved-courses/", views.saved_courses_view, name="saved_courses"),
    path("save-course/<int:course_id>/", views.toggle_save_course, name="toggle_save_course"),
    path("save-career/<int:profile_id>/", views.toggle_save_career, name="toggle_save_career"),

    # Applications
    path("applications/", views.applications_view, name="applications"),
    path("applications/add/", views.application_add, name="application_add"),
    path("applications/<int:pk>/update/", views.application_update, name="application_update"),
    path("applications/<int:pk>/delete/", views.application_delete, name="application_delete"),

    # Notifications
    path("notifications/", views.notifications_view, name="notifications"),
    path("notifications/mark-read/", views.mark_notifications_read, name="mark_notifications_read"),

    # ==============================
    # Allauth URLs (Google OAuth + built-in email/password)
    # ==============================
    path("", include("allauth.urls")),
    path("terms/", views.terms_view, name="terms"),
]