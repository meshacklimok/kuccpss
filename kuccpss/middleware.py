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
