from django.contrib import messages
from django.core.cache import cache
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import ResourceCategory, Resource, Article, SiteFeedback, SiteSetting, CalendarCycle


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
    cycles = list(CalendarCycle.objects.filter(is_active=True).prefetch_related("events"))
    current = next((c for c in cycles if c.is_current), None) or (cycles[0] if cycles else None)
    return render(request, "resources/calendar.html", {
        "cycles": cycles,
        "current_cycle": current,
        "calendar_intro": SiteSetting.get("calendar_intro"),
        "calendar_notice": SiteSetting.get("calendar_notice"),
    })


def how_to_guides(request):
    return render(request, "resources/guides.html")


@require_POST
def submit_feedback(request):
    feedback_type = request.POST.get('feedback_type', 'general')
    message = request.POST.get('message', '').strip()
    email = request.POST.get('email', '').strip()
    page_url = request.POST.get('page_url', '').strip()[:300]

    if not message:
        return JsonResponse({'ok': False, 'error': 'Message is required.'}, status=400)
    if len(message) > 2000:
        return JsonResponse({'ok': False, 'error': 'Message too long (max 2000 characters).'}, status=400)
    valid_types = {c[0] for c in SiteFeedback.TYPE_CHOICES}
    if feedback_type not in valid_types:
        feedback_type = 'general'

    SiteFeedback.objects.create(
        feedback_type=feedback_type,
        message=message,
        email=email,
        page_url=page_url,
    )
    return JsonResponse({'ok': True})


# ── Contact / support form ───────────────────────────────────────────────────
CONTACT_TOPICS = [
    ('account',  'Account or login'),
    ('payment',  'Payment or M-Pesa'),
    ('courses',  'Courses or cutoff data'),
    ('mentor',   'Mentorship'),
    ('other',    'Something else'),
]
CONTACT_LIMIT = 3          # messages per IP
CONTACT_WINDOW = 3600      # per hour


def contact(request):
    from kuccpss.email_utils import send_branded_email
    from kuccpss.ip_utils import get_client_ip
    from kuccpss.turnstile import verify_turnstile, FAILED_MESSAGE
    from django.conf import settings

    initial = {}
    if request.user.is_authenticated:
        initial = {'name': request.user.full_name or '', 'email': request.user.email}

    if request.method != 'POST':
        return render(request, 'resources/contact.html', {'topics': CONTACT_TOPICS, 'form': initial})

    form = {
        'name': request.POST.get('name', '').strip()[:100],
        'email': request.POST.get('email', '').strip()[:254],
        'topic': request.POST.get('topic', 'other'),
        'message': request.POST.get('message', '').strip(),
    }
    ctx = {'topics': CONTACT_TOPICS, 'form': form}

    # Honeypot: real users never see this field, so a filled value means a bot.
    if request.POST.get('website'):
        return redirect('resources:contact')

    errors = []
    if not form['name']:
        errors.append('Please enter your name.')
    try:
        validate_email(form['email'])
    except ValidationError:
        errors.append('Please enter a valid email so we can reply.')
    if len(form['message']) < 10:
        errors.append('Please tell us a little more (at least 10 characters).')
    elif len(form['message']) > 2000:
        errors.append('Message too long (max 2000 characters).')
    topic_labels = dict(CONTACT_TOPICS)
    if form['topic'] not in topic_labels:
        form['topic'] = 'other'
    if errors:
        for e in errors:
            messages.error(request, e)
        return render(request, 'resources/contact.html', ctx)

    if not verify_turnstile(request):
        messages.error(request, FAILED_MESSAGE)
        return render(request, 'resources/contact.html', ctx)

    key = f"contact:{get_client_ip(request)}"
    cache.add(key, 0, CONTACT_WINDOW)
    try:
        hits = cache.incr(key)
    except ValueError:
        cache.set(key, 1, CONTACT_WINDOW)
        hits = 1
    if hits > CONTACT_LIMIT:
        messages.error(request, 'Too many messages from this connection. Please try again in an hour.')
        return render(request, 'resources/contact.html', ctx)

    topic = topic_labels[form['topic']]
    SiteFeedback.objects.create(
        feedback_type='general',
        message=f"[Support: {topic}] {form['name']}\n\n{form['message']}",
        email=form['email'],
        page_url='/resources/contact/',
    )
    to = SiteSetting.get('admin_email', default=settings.ADMIN_EMAIL)
    send_branded_email(
        to=to,
        subject=f"Support request: {topic} ({form['name']})",
        heading="New support request",
        banner_label="Contact form",
        banner_color="blue",
        greeting="Hi Admin,",
        body_lines=[form['message']],
        table_rows=[
            {"label": "Name", "value": form['name']},
            {"label": "Reply to", "value": form['email'], "highlight": True},
            {"label": "Topic", "value": topic},
            {"label": "Signed in as", "value": request.user.email if request.user.is_authenticated else "Guest"},
        ],
    )
    messages.success(request, "Thanks. We've received your message and will reply by email.")
    return redirect('resources:contact')
