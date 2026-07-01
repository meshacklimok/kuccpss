from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('',              views.analytics_dashboard, name='dashboard'),
    path('export/',       views.export_csv,           name='export_csv'),
    path('live-feed/',    views.live_feed_json,        name='live_feed'),
    path('mentors/',      views.mentor_analytics,      name='mentor_analytics'),
    path('affiliates/',   views.affiliate_analytics,   name='affiliate_analytics'),
    path('pwa-install/',  views.pwa_install,           name='pwa_install'),
    path('heartbeat/',    views.heartbeat,             name='heartbeat'),
    path('payments/',     views.payments_overview,     name='payments'),
    path('pages/',        views.pages_analytics,       name='pages'),
    path('actions/',      views.actions_analytics,     name='actions'),
    path('users/<uuid:user_pk>/', views.user_timeline, name='user_timeline'),
    path('insights/',      views.insights_dashboard, name='insights'),
    path('calculator/',    views.calculator_analytics, name='calculator_analytics'),
    path('career-engine/', views.career_engine_analytics, name='career_engine_analytics'),
    path('conversion/',    views.conversion_analytics, name='conversion_analytics'),
    path('retention/',     views.retention_analytics,  name='retention_analytics'),
    path('ai-chat/',       views.ai_chat_analytics,    name='ai_chat_analytics'),
]
