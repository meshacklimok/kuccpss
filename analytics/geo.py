"""
Lightweight GeoIP2 wrapper.

Requires the MaxMind GeoLite2-City database (.mmdb) placed at GEOIP_PATH.
Download free (after free registration) from:
  https://dev.maxmind.com/geoip/geolite2-free-geolocation-data

Falls back silently to ('', '') if the database file is missing.
The reader is opened once per process and reused — zero per-request overhead.
"""

import os
import logging

log = logging.getLogger(__name__)

_reader = None   # geoip2.database.Reader instance, or False if unavailable


def _get_reader():
    global _reader
    if _reader is not None:
        return _reader or None

    try:
        import geoip2.database
        from django.conf import settings
        db_path = os.path.join(getattr(settings, 'GEOIP_PATH', ''), 'GeoLite2-City.mmdb')
        if not os.path.isfile(db_path):
            log.debug('GeoLite2-City.mmdb not found at %s — geo tracking disabled', db_path)
            _reader = False
            return None
        _reader = geoip2.database.Reader(db_path)
        log.info('GeoIP2 reader opened: %s', db_path)
    except Exception as exc:
        log.debug('GeoIP2 unavailable: %s', exc)
        _reader = False
    return _reader or None


def get_location(ip: str) -> tuple[str, str]:
    """
    Return (country_name, region_name) for the given IP.
    region_name is the first-level subdivision (county in Kenya, state in US, etc.)
    Returns ('', '') if IP is blank, private, or database unavailable.
    """
    if not ip:
        return '', ''
    reader = _get_reader()
    if not reader:
        return '', ''
    try:
        r = reader.city(ip)
        country = r.country.name or ''
        region  = r.subdivisions.most_specific.name or ''
        return country, region
    except Exception:
        return '', ''
