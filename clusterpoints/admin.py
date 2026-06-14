# clusterpoints/admin.py
from django.contrib import admin
from .models import GradePoint, UserKCSEResult, SubjectResult, ClusterCalculationResult

# ------------------------
# GradePoint Admin
# ------------------------
@admin.register(GradePoint)
class GradePointAdmin(admin.ModelAdmin):
    list_display = ('grade', 'points')
    search_fields = ('grade',)
    ordering = ('-points',)


# ------------------------
# SubjectResult Inline for UserKCSEResult
# ------------------------
class SubjectResultInline(admin.TabularInline):
    model = SubjectResult
    extra = 0
    readonly_fields = ('subject', 'points')
    can_delete = False


# ------------------------
# UserKCSEResult Admin
# ------------------------
@admin.register(UserKCSEResult)
class UserKCSEResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_points', 'mean_grade', 'created_at')
    search_fields = ('user__email',)
    readonly_fields = ('total_points', 'mean_grade', 'created_at', 'updated_at')
    inlines = [SubjectResultInline]
    ordering = ('-created_at',)


# ------------------------
# ClusterCalculationResult Admin
# ------------------------
@admin.register(ClusterCalculationResult)
class ClusterCalculationResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'cluster', 'cluster_points', 'created_at')
    search_fields = ('user__email', 'cluster__name')
    readonly_fields = (
        'cluster_points', 'core_subject_total', 'aggregate_total',
        'weighted_calculation', 'created_at', 'updated_at'
    )
    filter_horizontal = ('subjects_used',)
    ordering = ('-cluster_points',)

    # Prevent manual addition or editing
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False