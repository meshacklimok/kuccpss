from django.core.cache import cache


_NO_BANNER = 'none'  # cached None is indistinguishable from a miss — store a marker instead


def deadline_banner(request):
    banner = cache.get('deadline_banner')
    if banner is None:
        from .models import DeadlineBanner
        banner = DeadlineBanner.objects.filter(is_active=True).first() or _NO_BANNER
        cache.set('deadline_banner', banner, 120)
    return {'deadline_banner': None if banner == _NO_BANNER else banner}


def _handle_url(base, handle):
    handle = handle.strip().lstrip('@')
    if not handle:
        return ''
    return handle if handle.startswith('http') else base + handle


def social_links(request):
    url = cache.get('whatsapp_group_url')
    if url is None:
        from .models import SiteSetting
        url = SiteSetting.get('whatsapp_group_url').strip()
        cache.set('whatsapp_group_url', url, 300)

    # Footer social icons — each is hidden when its setting is blank.
    from .models import SiteSetting
    return {
        'whatsapp_group_url': url,
        'facebook_url':  SiteSetting.get('facebook_url').strip(),
        'twitter_url':   _handle_url('https://x.com/', SiteSetting.get('twitter_handle')),
        'instagram_url': _handle_url('https://www.instagram.com/', SiteSetting.get('instagram_handle')),
    }
