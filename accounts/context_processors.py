from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from .models import Notification


def unread_notifications(request):
    count = 0
    if request.user.is_authenticated:
        cache_key = f'notif_unread:{request.user.pk}'
        count = cache.get(cache_key)
        if count is None:
            count = Notification.objects.filter(user=request.user, is_read=False).count()
            cache.set(cache_key, count, 60)
    return {
        "unread_notification_count": count,
        "VAPID_PUBLIC_KEY": settings.VAPID_PUBLIC_KEY,
        "GOOGLE_OAUTH_AVAILABLE": settings.GOOGLE_OAUTH_AVAILABLE,
    }


def active_announcements(request):
    cache_key = 'active_announcements'
    announcements = cache.get(cache_key)
    if announcements is None:
        from resources.models import Announcement
        from django.db.models import Q
        now = timezone.now()
        announcements = list(
            Announcement.objects.filter(is_active=True).filter(
                Q(starts_at__isnull=True) | Q(starts_at__lte=now)
            ).filter(
                Q(ends_at__isnull=True) | Q(ends_at__gte=now)
            ).order_by('-created_at')[:5]
        )
        cache.set(cache_key, announcements, 120)
    return {'site_announcements': announcements}
