class ReferralMiddleware:
    """Capture ?ref=CODE from URL → store in session for later attribution on registration."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        code = request.GET.get('ref', '').strip().upper()
        if code and len(code) <= 12 and not request.session.get('referral_code'):
            from accounts.models import Referral
            if Referral.objects.filter(code=code, converted=False).exists():
                request.session['referral_code'] = code
        return self.get_response(request)


class DisableHttp3Middleware:
    """
    Clears Cloudflare/Render's alt-svc header so browsers don't
    attempt HTTP/3 (QUIC), which fails on some Kenyan ISPs.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['alt-svc'] = 'clear'
        return response
