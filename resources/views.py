from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
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

    return render(request, "resources/resource_list.html", {
        "categories": categories,
        "page_obj": page_obj,
        "query": query,
        "active_category": category_slug,
    })


def resource_detail(request, slug):
    resource = get_object_or_404(Resource, slug=slug)
    resource.increment_download()
    return render(request, "resources/resource_detail.html", {"resource": resource})


def article_list(request):
    articles = Article.objects.filter(is_published=True)
    tag = request.GET.get("tag", "")
    if tag:
        articles = articles.filter(tags__icontains=tag)

    paginator = Paginator(articles, 9)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    return render(request, "resources/article_list.html", {
        "page_obj": page_obj,
        "active_tag": tag,
    })


def article_detail(request, slug):
    article = get_object_or_404(Article, slug=slug, is_published=True)
    related = Article.objects.filter(is_published=True).exclude(pk=article.pk)[:3]
    return render(request, "resources/article_detail.html", {
        "article": article,
        "related": related,
    })
