from unittest.mock import MagicMock, patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase

from kuccpss.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    _is_http_service_failure,
)


def _http_error(status):
    resp = MagicMock(status_code=status)
    return requests.HTTPError(response=resp)


class CircuitBreakerTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.breaker = CircuitBreaker(
            "test", _is_http_service_failure,
            failure_threshold=3, window=60, reset_timeout=60,
        )

    def _fail(self, exc):
        with self.assertRaises(type(exc)):
            with self.breaker.guard():
                raise exc

    def test_opens_after_threshold_service_failures(self):
        for _ in range(3):
            self._fail(requests.Timeout())
        self.assertTrue(self.breaker.is_open())
        with self.assertRaises(CircuitOpenError):
            with self.breaker.guard():
                self.fail("call should not run while circuit is open")

    def test_client_errors_do_not_trip(self):
        for _ in range(5):
            self._fail(_http_error(400))
        self.assertFalse(self.breaker.is_open())

    def test_5xx_and_429_trip(self):
        self._fail(_http_error(503))
        self._fail(_http_error(429))
        self._fail(requests.ConnectionError())
        self.assertTrue(self.breaker.is_open())

    def test_success_resets_failure_count(self):
        self._fail(requests.Timeout())
        self._fail(requests.Timeout())
        with self.breaker.guard():
            pass
        self._fail(requests.Timeout())
        self.assertFalse(self.breaker.is_open())

    def test_half_open_single_failure_reopens(self):
        for _ in range(3):
            self._fail(requests.Timeout())
        cache.delete(self.breaker._open_key)  # simulate reset_timeout expiring
        self.assertFalse(self.breaker.is_open())
        self._fail(requests.Timeout())
        self.assertTrue(self.breaker.is_open())

    def test_broken_cache_never_blocks_calls(self):
        with patch("kuccpss.circuit_breaker.cache.get", side_effect=Exception("down")):
            self.assertFalse(self.breaker.is_open())


class IntaSendBreakerIntegrationTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("payments.services.requests.get", side_effect=requests.Timeout())
    def test_status_fetch_stops_calling_when_open(self, mock_get):
        from payments.services import fetch_intasend_invoice
        for _ in range(10):
            self.assertIsNone(fetch_intasend_invoice("abc"))
        # 5 real attempts trip the breaker; the rest are refused without a request
        self.assertEqual(mock_get.call_count, 5)
