from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from .models import ResourceCategory, Resource, Article


def resource_list(request):
    categories = ResourceCategory.objects.prefetch_related("resources").all()
    resources = Resource.objects.select_related("category").all()

    category_slug = request.GET.get("category")
    if category_slug:
        resources = resources.filter(category__slug=category_slug)

    query = request.GET.get("q", "")
    if query:
        resources = resources.filter(title__icontains=query)

    paginator = Paginator(resources, 12)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        return render(request, "resources/_resource_items_partial.html", {
            "page_obj": page_obj,
            "query": query,
            "active_category": category_slug,
        })

    return render(request, "resources/resource_list.html", {
        "categories": categories,
        "page_obj": page_obj,
        "query": query,
        "active_category": category_slug,
    })


def resource_detail(request, slug):
    resource = get_object_or_404(Resource, slug=slug)
    resource.increment_download()
    from analytics.utils import log_download
    log_download(request, content_type='resource', object_id=resource.pk, object_name=resource.title)
    return render(request, "resources/resource_detail.html", {"resource": resource})


def article_list(request):
    articles = Article.objects.filter(is_published=True)

    query = request.GET.get("q", "").strip()
    tag = request.GET.get("tag", "").strip()

    if query:
        articles = articles.filter(title__icontains=query) | Article.objects.filter(
            is_published=True, excerpt__icontains=query
        ) | Article.objects.filter(is_published=True, content__icontains=query)
        articles = articles.distinct()
    if tag:
        articles = articles.filter(tags__icontains=tag)

    # Featured article (pinned) — shown in hero above the grid; also kept in the grid so All shows everything
    featured = articles.filter(featured=True).first()

    # Collect all unique tags from published articles for the filter cloud
    all_tags = set()
    for row in Article.objects.filter(is_published=True).values_list("tags", flat=True):
        for t in (row or "").split(","):
            t = t.strip()
            if t:
                all_tags.add(t)
    all_tags = sorted(all_tags)

    paginator = Paginator(articles, 9)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        return render(request, "resources/_article_items_partial.html", {
            "page_obj": page_obj,
            "active_tag": tag,
            "query": query,
        })

    return render(request, "resources/article_list.html", {
        "page_obj": page_obj,
        "featured": featured,
        "active_tag": tag,
        "query": query,
        "all_tags": all_tags,
    })


def article_detail(request, slug):
    article = get_object_or_404(Article, slug=slug, is_published=True)
    # Prefer related articles that share at least one tag
    article_tags = article.get_tags_list()
    related = []
    if article_tags:
        from django.db.models import Q
        q = Q()
        for t in article_tags:
            q |= Q(tags__icontains=t)
        related = list(Article.objects.filter(is_published=True).exclude(pk=article.pk).filter(q)[:3])
    if len(related) < 3:
        extra = Article.objects.filter(is_published=True).exclude(pk=article.pk).exclude(
            pk__in=[r.pk for r in related])[:3 - len(related)]
        related += list(extra)
    return render(request, "resources/article_detail.html", {
        "article": article,
        "related": related,
    })


def kuccps_calendar(request):
    return render(request, "resources/calendar.html")


def how_to_guides(request):
    return render(request, "resources/guides.html")
