"""
URL configuration for kuccpss project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from django.http import FileResponse, HttpResponse
from django.views.generic import TemplateView
from django.contrib.sitemaps.views import sitemap
import os
from accounts.views import dashboard_view, public_home_view, email_lead_capture
from kuccpss.search_views import api_search_suggest
from kuccpss.sitemaps import sitemaps


def serve_sw(_request):
    candidates = []
    if settings.STATIC_ROOT:
        candidates.append(os.path.join(settings.STATIC_ROOT, 'js', 'sw.js'))
    for d in getattr(settings, 'STATICFILES_DIRS', []):
        candidates.append(os.path.join(d, 'js', 'sw.js'))
    for sw_path in candidates:
        if os.path.exists(sw_path):
            return FileResponse(open(sw_path, 'rb'), content_type='application/javascript',
                                headers={'Service-Worker-Allowed': '/'})
    from django.http import Http404
    raise Http404('sw.js not found')

def health_check(_request):
    import json
    from django.db import connection
    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False
    status = 200 if db_ok else 503
    payload = {"status": "ok" if db_ok else "degraded", "db": db_ok}
    return HttpResponse(json.dumps(payload), content_type="application/json", status=status)


def serve_robots(request):
    from django.template.loader import render_to_string
    content = render_to_string('robots.txt', request=request)
    return HttpResponse(content, content_type='text/plain')

def serve_llms(request):
    from django.template.loader import render_to_string
    content = render_to_string('llms.txt', request=request)
    return HttpResponse(content, content_type='text/plain; charset=utf-8')

handler404 = 'django.views.defaults.page_not_found'
handler500 = 'django.views.defaults.server_error'

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('sw.js', serve_sw, name='service_worker'),
    path('robots.txt', serve_robots, name='robots_txt'),
    path('llms.txt', serve_llms, name='llms_txt'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('offline/', TemplateView.as_view(template_name='offline.html'), name='offline'),
    path('cn-staff/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('', public_home_view, name='home'),
    path('dashboard/', dashboard_view, name='dashboard_root'),
    path('clusterpoints/', include('clusterpoints.urls', namespace='clusterpoints')),
    path('accounts/', include('django.contrib.auth.urls')),
    path("accounts/", include("allauth.urls")),
    path('clusters/', include('clusters.urls', namespace='clusters')),
    path('institutions/', include('institutions.urls', namespace='institutions')),
    path('courses/', include('courses.urls', namespace='courses')),
    path('career.html', RedirectView.as_view(url='/career/', permanent=True)),
    path('career/', include('career.urls', namespace='career')),
    path('resources/', include('resources.urls', namespace='resources')),
    path('predictor/', include('predictor.urls', namespace='predictor')),
    path('payments/', include('payments.urls', namespace='payments')),
    path('api/search/', api_search_suggest, name='api_search_suggest'),
    path('api/email-lead/', email_lead_capture, name='email_lead_capture'),
    path('analytics/', include('analytics.urls', namespace='analytics')),
    path('mentorship/', include('mentorship.urls', namespace='mentorship')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    from django.views.defaults import page_not_found, server_error
    urlpatterns += [
        path('errors/404/', lambda r: page_not_found(r, None)),
        path('errors/500/', lambda r: server_error(r)),
    ]
