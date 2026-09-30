"""
Cache-backed circuit breaker for outbound calls to external services
(OpenAI, IntaSend/M-Pesa).

When a service fails ``failure_threshold`` times within ``window`` seconds,
the circuit "opens" for ``reset_timeout`` seconds: calls fail instantly with
``CircuitOpenError`` instead of tying up a gunicorn worker waiting on a
timeout. After that, calls are let through again (half-open); the failure
count is left one short of the threshold, so a single further failure
re-opens the circuit immediately, while a success resets it.

State lives in the default Django cache, so it is shared across workers when
Redis is configured and per-process with LocMemCache.

Only *service* failures count (timeouts, connection errors, 5xx, 429) —
client errors such as a bad phone number never trip the breaker.
"""
import logging
from contextlib import contextmanager

from django.core.cache import cache

logger = logging.getLogger(__name__)


class CircuitOpenError(Exception):
    """Raised when a call is refused because the circuit is open."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"{name} is temporarily unavailable (circuit open)")


class CircuitBreaker:
    def __init__(self, name: str, is_failure, failure_threshold: int = 5,
                 window: int = 60, reset_timeout: int = 60):
        self.name = name
        self.is_failure = is_failure
        self.failure_threshold = failure_threshold
        self.window = window
        self.reset_timeout = reset_timeout
        self._fail_key = f"cb:{name}:failures"
        self._open_key = f"cb:{name}:open"

    def is_open(self) -> bool:
        try:
            return bool(cache.get(self._open_key))
        except Exception:
            return False  # a broken cache must never block real calls

    def record_success(self) -> None:
        try:
            cache.delete(self._fail_key)
        except Exception:
            pass

    def record_failure(self) -> None:
        try:
            cache.add(self._fail_key, 0, self.window)
            failures = cache.incr(self._fail_key)
        except Exception:
            return
        if failures >= self.failure_threshold:
            cache.set(self._open_key, True, self.reset_timeout)
            # Keep the count one short so the first failure after reopening
            # trips the circuit again straight away.
            cache.set(self._fail_key, self.failure_threshold - 1,
                      self.reset_timeout + self.window)
            logger.warning("Circuit '%s' OPEN for %ss after %s failures",
                           self.name, self.reset_timeout, failures)

    @contextmanager
    def guard(self):
        """Wrap an outbound call: ``with breaker.guard(): client.call()``."""
        if self.is_open():
            raise CircuitOpenError(self.name)
        try:
            yield
        except Exception as exc:
            if self.is_failure(exc):
                self.record_failure()
            raise
        else:
            self.record_success()


# ── Failure classifiers ──────────────────────────────────────────────────────

def _is_http_service_failure(exc: Exception) -> bool:
    import requests
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code >= 500 or exc.response.status_code == 429
    return False


def _is_openai_service_failure(exc: Exception) -> bool:
    try:
        import openai
    except ImportError:
        return False
    return isinstance(exc, (
        openai.APITimeoutError,
        openai.APIConnectionError,
        openai.InternalServerError,
        openai.RateLimitError,
    ))


# ── Breakers ─────────────────────────────────────────────────────────────────

ai_breaker = CircuitBreaker("openai", _is_openai_service_failure)
intasend_breaker = CircuitBreaker("intasend", _is_http_service_failure)


def get_openai_client(api_key: str):
    """
    OpenAI client with bounded timeouts. The SDK default (600s, 2 retries)
    can hold a gunicorn worker for many minutes during an outage.
    """
    from openai import OpenAI
    return OpenAI(api_key=api_key, timeout=45.0, max_retries=1)
