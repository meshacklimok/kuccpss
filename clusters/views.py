from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.views.decorators.cache import cache_page
from .models import Cluster, SubjectGroup, Subject
from .forms import ClusterForm, SubjectGroupForm

# =====================================================
# 1️⃣ LIST ALL CLUSTERS
# =====================================================
@cache_page(60 * 20)  # 20-minute cache — cluster list is static reference data
def cluster_list(request):
    # The 18 KUCCPS clusters (rows 101–118); degree courses link to them directly
    clusters = (
        Cluster.objects
        .kuccps()
        .annotate(course_count=Count('course'))
        .order_by('number')
    )
    context = {
        'cluster_groups': [
            {'number': c.kuccps_number, 'label': c.name, 'cluster': c, 'total_courses': c.course_count}  # type: ignore[attr-defined]
            for c in clusters
        ],
    }
    return render(request, 'clusters/cluster_list.html', context)


# =====================================================
# 2️⃣ CLUSTER DETAIL
# =====================================================
def cluster_detail(request, slug):
    from courses.models import Course
    cluster = get_object_or_404(Cluster, slug=slug)
    subject_groups = cluster.subject_groups.prefetch_related('subjects').all()  # type: ignore[attr-defined]
    courses = (
        Course.objects
        .filter(cluster=cluster)
        .select_related('course_type')
        .order_by('name')
    )

    context = {
        'cluster': cluster,
        'subject_groups': subject_groups,
        'courses': courses,
        'main_num': cluster.kuccps_number,
    }
    return render(request, 'clusters/cluster_detail.html', context)


# =====================================================
# 2b. CLUSTER COURSES — all courses for a cluster (gated)
# =====================================================
def cluster_courses(request, slug):
    from courses.models import Course
    from payments.services import has_paid_for_feature, is_feature_enabled, price_for_feature

    cluster = get_object_or_404(Cluster, slug=slug)
    all_courses = (
        Course.objects
        .filter(cluster=cluster)
        .select_related('course_type')
        .prefetch_related('offerings__institution')
        .order_by('name')
    )
    total_count = all_courses.count()
    free_courses = list(all_courses[:5])
    paid_courses = list(all_courses[5:])

    is_locked = (
        request.user.is_authenticated
        and is_feature_enabled('view_eligible_courses')
        and not has_paid_for_feature(request.user, 'view_eligible_courses')
    )

    return render(request, 'clusters/cluster_courses.html', {
        'cluster': cluster,
        'free_courses': free_courses,
        'paid_courses': paid_courses,
        'total_count': total_count,
        'is_locked': is_locked,
        'gate_feature': 'view_eligible_courses',
        'gate_price': price_for_feature('view_eligible_courses'),
    })


# =====================================================
# 3️⃣ CREATE CLUSTER (Front-end Optional)
# =====================================================
@login_required
def cluster_create(request):
    """
    Allows creating a new cluster via front-end form.
    Only accessible to logged-in users (e.g., admin).
    """
    if request.method == 'POST':
        form = ClusterForm(request.POST, request.FILES)
        if form.is_valid():
            cluster = form.save()
            messages.success(request, f"Cluster '{cluster.name}' created successfully.")
            return redirect(cluster.get_absolute_url())
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ClusterForm()

    return render(request, 'clusters/cluster_form.html', {'form': form, 'title': 'Create Cluster'})


# =====================================================
# 4️⃣ EDIT CLUSTER
# =====================================================
@login_required
def cluster_edit(request, slug):
    """
    Allows editing an existing cluster.
    """
    cluster = get_object_or_404(Cluster, slug=slug)

    if request.method == 'POST':
        form = ClusterForm(request.POST, request.FILES, instance=cluster)
        if form.is_valid():
            form.save()
            messages.success(request, f"Cluster '{cluster.name}' updated successfully.")
            return redirect(cluster.get_absolute_url())
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ClusterForm(instance=cluster)

    return render(request, 'clusters/cluster_form.html', {'form': form, 'title': f'Edit Cluster: {cluster.name}'})


# =====================================================
# 5️⃣ CREATE SUBJECT GROUP UNDER CLUSTER
# =====================================================
@login_required
def subject_group_create(request, cluster_slug):
    """
    Create a new subject group under a specific cluster.
    """
    cluster = get_object_or_404(Cluster, slug=cluster_slug)

    if request.method == 'POST':
        form = SubjectGroupForm(request.POST)
        if form.is_valid():
            subject_group = form.save(commit=False)
            subject_group.cluster = cluster
            subject_group.save()
            form.save_m2m()  # Save ManyToMany subjects
            messages.success(request, f"Subject group '{subject_group.name}' created for {cluster.name}.")
            return redirect('clusters:cluster_detail', slug=cluster.slug)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = SubjectGroupForm()

    return render(request, 'clusters/subject_group_form.html', {
        'form': form,
        'cluster': cluster,
        'title': f"Add Subject Group to {cluster.name}"
    })


# =====================================================
# 6️⃣ EDIT SUBJECT GROUP
# =====================================================
@login_required
def subject_group_edit(request, group_id):
    """
    Edit an existing subject group.
    """
    group = get_object_or_404(SubjectGroup, id=group_id)
    cluster = group.cluster

    if request.method == 'POST':
        form = SubjectGroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            messages.success(request, f"Subject group '{group.name}' updated successfully.")
            return redirect('clusters:cluster_detail', slug=cluster.slug)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = SubjectGroupForm(instance=group)

    return render(request, 'clusters/subject_group_form.html', {
        'form': form,
        'cluster': cluster,
        'title': f"Edit Subject Group: {group.name}"
    })