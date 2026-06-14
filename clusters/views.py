import re
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from .models import Cluster, SubjectGroup, Subject
from .forms import ClusterForm, SubjectGroupForm

CLUSTER_LABELS = {
    1:  'Law, Commerce & Business',
    2:  'Business, Management & Information',
    3:  'Communication, Media & Social Sciences',
    4:  'Geospatial & Earth Sciences',
    5:  'Engineering & Applied Sciences',
    6:  'Architecture, Real Estate & ICT',
    7:  'Computer Science & IT',
    8:  'Agricultural Economics',
    9:  'Pure Sciences',
    10: 'Economics, Finance & Actuarial',
    11: 'Fashion & Textile',
    12: 'Sports & Health Promotion',
    13: 'Medicine, Health & Allied',
    14: 'History & Archaeology',
    15: 'Agriculture, Veterinary & Environment',
    16: 'Geography & Land Management',
    17: 'French & German',
    18: 'Music',
    19: 'Education',
    20: 'Religious Studies & Theology',
}

def _main_num(cluster):
    m = re.search(r'\((\d+)[A-K]\)', cluster.name)
    return int(m.group(1)) if m else (cluster.number or 0)


# =====================================================
# 1️⃣ LIST ALL CLUSTERS
# =====================================================
def cluster_list(request):
    clusters = (
        Cluster.objects
        .exclude(number__gte=100)          # exclude master calculation clusters (101-120)
        .annotate(course_count=Count('course'))
        .order_by('number', 'name')
    )

    groups = {}
    for cluster in clusters:
        num = _main_num(cluster)
        # Attach extracted sub-cluster code (e.g. "1A") for display
        mc = re.search(r'\((\d+[A-K])\)', cluster.name)
        cluster.code = mc.group(1) if mc else cluster.name
        if num not in groups:
            groups[num] = {
                'number': num,
                'label': CLUSTER_LABELS.get(num, f'Cluster {num}'),
                'sub_clusters': [],
                'total_courses': 0,
            }
        groups[num]['sub_clusters'].append(cluster)
        groups[num]['total_courses'] += cluster.course_count

    context = {
        'cluster_groups': sorted(groups.values(), key=lambda g: g['number']),
    }
    return render(request, 'clusters/cluster_list.html', context)


# =====================================================
# 2️⃣ CLUSTER DETAIL
# =====================================================
_REQ_SPLIT = re.compile(r'(?<=[+)])\s+(?=[A-Z/])')

def _parse_requirements(desc):
    """Split a raw requirements string into individual subject-grade pairs."""
    if not desc or desc.startswith('KUCCPS sub-cluster'):
        return []
    parts = _REQ_SPLIT.split(desc)
    return [p.strip() for p in parts if p.strip()]


def cluster_detail(request, slug):
    from courses.models import Course
    cluster = get_object_or_404(Cluster, slug=slug)
    subject_groups = cluster.subject_groups.prefetch_related('subjects').all()
    courses = (
        Course.objects
        .filter(cluster=cluster)
        .select_related('course_type')
        .order_by('name')
    )

    num = _main_num(cluster)
    context = {
        'cluster': cluster,
        'subject_groups': subject_groups,
        'courses': courses,
        'main_num': num,
        'main_label': CLUSTER_LABELS.get(num, ''),
        'requirements': _parse_requirements(cluster.description),
    }
    return render(request, 'clusters/cluster_detail.html', context)


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
            messages.success(request, f"Cluster '{cluster.name}' created successfully!")
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
            messages.success(request, f"Cluster '{cluster.name}' updated successfully!")
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
            messages.success(request, f"Subject group '{group.name}' updated successfully!")
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