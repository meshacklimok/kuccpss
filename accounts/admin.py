from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User,
    EmailVerificationToken,
    RememberToken,
    DeviceSession,
    LoginHistory,
    SavedCourse,
    SavedCareer,
    ApplicationTracking,
    Notification,
)
from .forms import UserAdminCreationForm, UserAdminChangeForm

# =====================================================
# CUSTOM USER ADMIN
# =====================================================
class UserAdmin(BaseUserAdmin):
    # Forms for adding and changing users
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm

    # Fields to display in admin list view
    list_display = ('email', 'full_name', 'is_staff', 'is_verified', 'is_active', 'is_suspended')
    list_filter = ('is_staff', 'is_verified', 'is_active', 'is_suspended')
    search_fields = ('email', 'full_name')
    ordering = ('email',)
    readonly_fields = ('last_login', 'created_at', 'updated_at', 'deleted_at')

    # Fieldsets for changing a user
    fieldsets = (
        (None, {'fields': ('email', 'full_name', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified', 'is_suspended', 'groups', 'user_permissions')}),
        ('Compliance', {'fields': ('agreed_terms', 'terms_version')}),
        ('Timestamps', {'fields': ('last_login', 'created_at', 'updated_at', 'deleted_at')}),
    )

    # Fieldsets for adding a user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'password1', 'password2', 'is_staff', 'is_superuser', 'is_verified', 'agreed_terms')
        }),
    )


# =====================================================
# EMAIL VERIFICATION TOKEN ADMIN
# =====================================================
@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'is_used', 'expires_at', 'created_at')
    list_filter = ('is_used', 'expires_at')
    search_fields = ('user__email', 'token')
    readonly_fields = ('created_at',)


# =====================================================
# REMEMBER TOKEN ADMIN
# =====================================================
@admin.register(RememberToken)
class RememberTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'is_active', 'expires_at', 'ip_address', 'user_agent', 'created_at')
    list_filter = ('is_active', 'expires_at')
    search_fields = ('user__email', 'token', 'ip_address', 'user_agent')
    readonly_fields = ('created_at',)


# =====================================================
# DEVICE SESSION ADMIN
# =====================================================
@admin.register(DeviceSession)
class DeviceSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'session_key', 'device_name', 'ip_address', 'is_active', 'last_activity', 'created_at')
    list_filter = ('is_active', 'last_activity')
    search_fields = ('user__email', 'session_key', 'device_name', 'ip_address')
    readonly_fields = ('created_at', 'last_activity')


# =====================================================
# LOGIN HISTORY ADMIN
# =====================================================
@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'ip_address', 'user_agent', 'success', 'login_time', 'logout_time')
    list_filter = ('success', 'login_time')
    search_fields = ('user__email', 'ip_address', 'user_agent')
    readonly_fields = ('login_time', 'logout_time')
    

# =====================================================
# REGISTER CUSTOM USER MODEL
# =====================================================
admin.site.register(User, UserAdmin)


# =====================================================
# SAVED COURSES
# =====================================================
@admin.register(SavedCourse)
class SavedCourseAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'saved_at')
    list_filter = ('saved_at',)
    search_fields = ('user__email', 'course__name')
    readonly_fields = ('saved_at',)


# =====================================================
# SAVED CAREERS
# =====================================================
@admin.register(SavedCareer)
class SavedCareerAdmin(admin.ModelAdmin):
    list_display = ('user', 'career_profile', 'saved_at')
    list_filter = ('saved_at',)
    search_fields = ('user__email', 'career_profile__title')
    readonly_fields = ('saved_at',)


# =====================================================
# APPLICATION TRACKING
# =====================================================
@admin.register(ApplicationTracking)
class ApplicationTrackingAdmin(admin.ModelAdmin):
    list_display = ('user', 'course_name', 'institution_name', 'status', 'deadline', 'created_at')
    list_filter = ('status', 'deadline', 'created_at')
    search_fields = ('user__email', 'course_name', 'institution_name')
    readonly_fields = ('created_at', 'updated_at')


# =====================================================
# NOTIFICATIONS
# =====================================================
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notif_type', 'is_read', 'message_preview', 'created_at')
    list_filter = ('notif_type', 'is_read', 'created_at')
    search_fields = ('user__email', 'message')
    readonly_fields = ('created_at',)

    def message_preview(self, obj):
        return obj.message[:60]
    message_preview.short_description = "Message"