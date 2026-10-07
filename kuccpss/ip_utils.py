import ipaddress
from functools import lru_cache

# Cloudflare's published edge ranges (https://www.cloudflare.com/ips/).
# Refresh if Cloudflare announces new ranges; a missing range only means
# requests through it fall back to the edge IP, never that a spoof is trusted.
CLOUDFLARE_IP_RANGES = (
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
    "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
    "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
    "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32",
    "2405:8100::/32", "2a06:98c0::/29", "2c0f:f248::/32",
)


@lru_cache(maxsize=1)
def _cloudflare_networks():
    return tuple(ipaddress.ip_network(cidr) for cidr in CLOUDFLARE_IP_RANGES)


def _parse_ip(value: str):
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def is_cloudflare_ip(value: str) -> bool:
    ip = _parse_ip(value)
    return ip is not None and any(ip in net for net in _cloudflare_networks())


def get_client_ip(request) -> str:
    """
    Canonical client-IP resolver, shared by every place in the codebase that needs
    a request's IP (rate limiting, analytics, login history).

    Trusts the *last* entry in X-Forwarded-For, not the first — Render's edge proxy
    appends the address that connected to it, so trusting the first entry lets a
    client spoof its own IP by sending a forged X-Forwarded-For header.

    With Cloudflare proxying in front of Render, that last entry is a Cloudflare
    edge, not the visitor. Only then is CF-Connecting-IP (set by Cloudflare to the
    real visitor) trusted; a request hitting Render directly can't use the header
    to spoof its IP, because its last hop isn't a Cloudflare address.
    """
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    peer = x_forwarded.split(',')[-1].strip() if x_forwarded else (request.META.get('REMOTE_ADDR', '') or '')

    if peer and is_cloudflare_ip(peer):
        cf_ip = request.META.get('HTTP_CF_CONNECTING_IP', '').strip()
        if cf_ip and _parse_ip(cf_ip) is not None:
            return cf_ip
    return peer
