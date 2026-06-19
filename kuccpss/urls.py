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
from django.conf import settings
from django.conf.urls.static import static
from django.http import FileResponse
import os
from accounts.views import dashboard_view, public_home_view
from kuccpss.search_views import api_search_suggest


def serve_sw(_request):
    sw_path = os.path.join(settings.STATIC_ROOT or os.path.join(settings.BASE_DIR, 'static'), 'js', 'sw.js')
    return FileResponse(open(sw_path, 'rb'), content_type='application/javascript',
                        headers={'Service-Worker-Allowed': '/'})

handler404 = 'django.views.defaults.page_not_found'
handler500 = 'django.views.defaults.server_error'

urlpatterns = [
    path('sw.js', serve_sw, name='service_worker'),
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
    path('career/', include('career.urls', namespace='career')),
    path('resources/', include('resources.urls', namespace='resources')),
    path('predictor/', include('predictor.urls', namespace='predictor')),
    path('payments/', include('payments.urls', namespace='payments')),
    path('api/search/', api_search_suggest, name='api_search_suggest'),
    path('analytics/', include('analytics.urls', namespace='analytics')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    from django.views.defaults import page_not_found, server_error
    urlpatterns += [
        path('errors/404/', lambda r: page_not_found(r, None)),
        path('errors/500/', lambda r: server_error(r)),
    ]
