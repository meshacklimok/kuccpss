import time
from functools import wraps
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

REAUTH_WINDOW_SECONDS = 30 * 60  # 30 minutes


def require_recent_auth(view_func):
    """
    Require the user to have verified their password within the last 30 minutes.
    If not, redirect to the re-auth page and return afterwards.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/accounts/login/?next={request.get_full_path()}')
        last_verified = request.session.get('_auth_verified_at', 0)
        if time.time() - last_verified > REAUTH_WINDOW_SECONDS:
            params = urlencode({'next': request.get_full_path()})
            return redirect(f'/accounts/re-auth/?{params}')
        return view_func(request, *args, **kwargs)
    return wrapper
