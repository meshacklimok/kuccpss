from django.core.cache import cache


def deadline_banner(request):
    banner = cache.get('deadline_banner')
    if banner is None:
        from .models import DeadlineBanner
        banner = DeadlineBanner.objects.filter(is_active=True).first()
        cache.set('deadline_banner', banner, 120)
    return {'deadline_banner': banner}
