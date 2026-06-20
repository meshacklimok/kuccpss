from django.conf import settings
from .models import Notification


def unread_notifications(request):
    count = 0
    if request.user.is_authenticated:
        count = Notification.objects.filter(user=request.user, is_read=False).count()
    return {
        "unread_notification_count": count,
        "VAPID_PUBLIC_KEY": settings.VAPID_PUBLIC_KEY,
        "GOOGLE_OAUTH_AVAILABLE": settings.GOOGLE_OAUTH_AVAILABLE,
    }
