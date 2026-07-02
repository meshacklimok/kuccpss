def get_client_ip(request) -> str:
    """
    Canonical client-IP resolver, shared by every place in the codebase that needs
    a request's IP (rate limiting, analytics, login history).

    Trusts the *last* entry in X-Forwarded-For, not the first — Render's edge proxy
    appends the real client IP at the end of the chain, so trusting the first entry
    lets a client spoof its own IP by sending a forged X-Forwarded-For header.
    """
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if x_forwarded:
        return x_forwarded.split(',')[-1].strip()
    return request.META.get('REMOTE_ADDR', '') or ''
