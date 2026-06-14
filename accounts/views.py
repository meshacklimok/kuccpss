import secrets
from typing import Any, Dict
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_http_methods
from django.http import HttpRequest, HttpResponse

from .forms import UserRegistrationForm, UserLoginForm
from .models import (
    User,
    EmailVerificationToken,
    RememberToken,
    DeviceSession,
)


# =====================================================
# Helper
# =====================================================
def get_client_ip(request: HttpRequest) -> str:
    """Return the client IP address from request."""
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


# =====================================================
# REGISTER VIEW (Class-Based)
# =====================================================
class RegisterView(View):
    template_name = "accounts/register.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect("accounts:dashboard")
        form = UserRegistrationForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request: HttpRequest) -> HttpResponse:
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True
            user.is_verified = True
            user.save()

            # Generate email verification token
            token = secrets.token_urlsafe(32)
            EmailVerificationToken.objects.create(user=user, token=token)

            # TODO: Send verification email with token
            messages.success(
                request, "Account created. Check your email to verify your account."
            )
            return redirect("accounts:login")

        return render(request, self.template_name, {"form": form})


# =====================================================
# EMAIL VERIFICATION VIEW
# =====================================================
@require_http_methods(["GET"])
def email_verify_view(request: HttpRequest, token: str) -> HttpResponse:
    verification = get_object_or_404(
        EmailVerificationToken, token=token, is_used=False
    )
    if not verification.is_valid():
        messages.error(request, "Verification link is invalid or expired.")
        return redirect("accounts:login")

    user = verification.user
    user.is_verified = True
    user.save(update_fields=["is_verified"])

    verification.is_used = True
    verification.save(update_fields=["is_used"])

    messages.success(request, "Email verified successfully. You may now log in.")
    return redirect("accounts:login")


# =====================================================
# LOGIN VIEW (Class-Based)
# =====================================================
class LoginView(View):
    template_name = "accounts/login.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect("accounts:dashboard")
        form = UserLoginForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request: HttpRequest) -> HttpResponse:
        form = UserLoginForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data["user"]

            # Enforce account status
            if not user.is_active:
                messages.error(request, "Your account is deactivated.")
                return redirect("accounts:login")
            if user.is_suspended:
                messages.error(request, "Your account is suspended.")
                return redirect("accounts:login")
            if not user.is_verified:
                messages.error(request, "You must verify your email before login.")
                return redirect("accounts:login")

            login(request, user)

            # Remember me token
            remember_me = form.cleaned_data.get("remember_me")
            if remember_me:
                token = secrets.token_urlsafe(32)
                expires_at = timezone.now() + timezone.timedelta(hours=72)
                RememberToken.objects.create(
                    user=user,
                    token=token,
                    expires_at=expires_at,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                )
                request.session.set_expiry(604800)  # 7 days
            else:
                request.session.set_expiry(0)  # Browser close

            messages.success(
                request, f"Welcome back, {user.full_name or user.email}!"
            )
            return redirect("accounts:dashboard")

        return render(request, self.template_name, {"form": form})


# =====================================================
# LOGOUT VIEW
# =====================================================
@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    messages.info(request, "Logged out successfully.")
    return redirect("accounts:login")


# =====================================================
# DASHBOARD VIEW
# =====================================================
@login_required
def dashboard_view(request: HttpRequest) -> HttpResponse:
    user = request.user
    if not user.is_verified:
        messages.warning(request, "You must verify your email to access the dashboard.")
        return redirect("accounts:login")
    if not user.is_active or user.is_suspended:
        messages.error(request, "Your account is inactive or suspended.")
        return redirect("accounts:login")

    from clusterpoints.models import UserKCSEResult, ClusterCalculationResult
    from .models import SavedCourse, ApplicationTracking, Notification
    from career.models import CareerProfile

    latest_result = UserKCSEResult.objects.filter(user=user).order_by("-created_at").first()

    cluster_results = []
    eligible_count = 0
    if latest_result:
        cluster_results = list(
            ClusterCalculationResult.objects.filter(kcse_result=latest_result)
            .select_related("cluster").order_by("-cluster_points")[:8]
        )
        # count courses user qualifies for (has cluster points >= cutoff)
        from courses.models import Course
        for course in Course.objects.filter(cluster__isnull=False).select_related("cluster"):
            if not course.cutoff_points:
                continue
            year_key = str(2024)
            cutoff = course.cutoff_points.get(year_key) or course.cutoff_points.get(
                max(course.cutoff_points.keys(), default="")
            )
            if cutoff is None:
                continue
            match = next((r for r in cluster_results if r.cluster_id == course.cluster_id), None)
            if match and match.cluster_points >= float(cutoff):
                eligible_count += 1

    saved_count = SavedCourse.objects.filter(user=user).count()
    applications = ApplicationTracking.objects.filter(user=user)
    notifications = Notification.objects.filter(user=user, is_read=False).order_by("-created_at")[:5]
    unread_count = Notification.objects.filter(user=user, is_read=False).count()
    recommended_careers = CareerProfile.objects.all()[:3]

    return render(request, "accounts/dashboard.html", {
        "latest_result": latest_result,
        "cluster_results": cluster_results,
        "eligible_count": eligible_count,
        "saved_count": saved_count,
        "applications": applications,
        "notifications": notifications,
        "unread_count": unread_count,
        "recommended_careers": recommended_careers,
    })


# =====================================================
# PROFILE UPDATE VIEW (Removed Profile model)
# =====================================================
@login_required
def profile_update_view(request: HttpRequest) -> HttpResponse:
    """
    Update user fields directly (no Profile model).
    """
    from .forms import UserProfileForm  # create a form that edits User fields

    form = UserProfileForm(request.POST or None, instance=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, "Profile updated successfully.")
        return redirect("accounts:profile")

    return render(request, "accounts/profile.html", {"form": form})


# =====================================================
# PASSWORD CHANGE VIEW
# =====================================================
@login_required
@require_http_methods(["GET", "POST"])
def change_password_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")
        if not password1 or password1 != password2:
            messages.error(request, "Passwords do not match.")
        else:
            request.user.set_password(password1)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "Password changed successfully.")
            return redirect("accounts:dashboard")

    return render(request, "accounts/change_password.html")



def terms_view(request):
    from datetime import datetime
    return render(request, "accounts/terms.html", {"year": datetime.now().year})


# =====================================================
# SAVED COURSES
# =====================================================
@login_required
def saved_courses_view(request: HttpRequest) -> HttpResponse:
    from .models import SavedCourse
    saved = SavedCourse.objects.filter(user=request.user).select_related("course__course_type")
    return render(request, "accounts/saved_courses.html", {"saved": saved})


@login_required
@require_http_methods(["POST"])
def toggle_save_course(request: HttpRequest, course_id: int) -> HttpResponse:
    from django.http import JsonResponse
    from .models import SavedCourse
    from courses.models import Course
    course = get_object_or_404(Course, pk=course_id)
    obj, created = SavedCourse.objects.get_or_create(user=request.user, course=course)
    if not created:
        obj.delete()
        return JsonResponse({"saved": False, "message": "Removed from saved"})
    return JsonResponse({"saved": True, "message": "Course saved!"})


@login_required
@require_http_methods(["POST"])
def toggle_save_career(request: HttpRequest, profile_id: int) -> HttpResponse:
    from django.http import JsonResponse
    from .models import SavedCareer
    from career.models import CareerProfile
    profile = get_object_or_404(CareerProfile, pk=profile_id)
    obj, created = SavedCareer.objects.get_or_create(user=request.user, career_profile=profile)
    if not created:
        obj.delete()
        return JsonResponse({"saved": False})
    return JsonResponse({"saved": True})


# =====================================================
# APPLICATION TRACKING
# =====================================================
@login_required
def applications_view(request: HttpRequest) -> HttpResponse:
    from .models import ApplicationTracking
    apps = ApplicationTracking.objects.filter(user=request.user)
    return render(request, "accounts/applications.html", {"applications": apps})


@login_required
def application_add(request: HttpRequest) -> HttpResponse:
    from .models import ApplicationTracking
    from .forms import ApplicationForm
    form = ApplicationForm(request.POST or None)
    if form.is_valid():
        app = form.save(commit=False)
        app.user = request.user
        app.save()
        messages.success(request, "Application added.")
        return redirect("accounts:applications")
    return render(request, "accounts/application_form.html", {"form": form, "action": "Add"})


@login_required
def application_update(request: HttpRequest, pk: int) -> HttpResponse:
    from .models import ApplicationTracking
    from .forms import ApplicationForm
    app = get_object_or_404(ApplicationTracking, pk=pk, user=request.user)
    form = ApplicationForm(request.POST or None, instance=app)
    if form.is_valid():
        form.save()
        messages.success(request, "Application updated.")
        return redirect("accounts:applications")
    return render(request, "accounts/application_form.html", {"form": form, "action": "Update"})


@login_required
@require_http_methods(["POST"])
def application_delete(request: HttpRequest, pk: int) -> HttpResponse:
    from .models import ApplicationTracking
    app = get_object_or_404(ApplicationTracking, pk=pk, user=request.user)
    app.delete()
    messages.success(request, "Application removed.")
    return redirect("accounts:applications")


# =====================================================
# NOTIFICATIONS
# =====================================================
@login_required
def notifications_view(request: HttpRequest) -> HttpResponse:
    from .models import Notification
    notifs = Notification.objects.filter(user=request.user)
    notifs.filter(is_read=False).update(is_read=True)
    return render(request, "accounts/notifications.html", {"notifications": notifs})


@login_required
@require_http_methods(["POST"])
def mark_notifications_read(request: HttpRequest) -> HttpResponse:
    from django.http import JsonResponse
    from .models import Notification
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"status": "ok"})