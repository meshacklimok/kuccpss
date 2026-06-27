from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('',             views.analytics_dashboard, name='dashboard'),
    path('export/',      views.export_csv,           name='export_csv'),
    path('live-feed/',   views.live_feed_json,       name='live_feed'),
    path('mentors/',     views.mentor_analytics,     name='mentor_analytics'),
    path('affiliates/',  views.affiliate_analytics,  name='affiliate_analytics'),
    path('pwa-install/', views.pwa_install,          name='pwa_install'),
]
