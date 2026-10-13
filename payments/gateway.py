"""
Picks which M-Pesa gateway takes a payment (IntaSend or Daraja) from the admin-editable
PaymentGatewayConfig, and falls back to the other one when the first is down.
The IntaSend and Daraja clients themselves live in services.py / daraja.py.
"""
import logging

import requests
from django.conf import settings

from kuccpss.circuit_breaker import CircuitOpenError, daraja_breaker, intasend_breaker

from . import daraja, services
from .models import PaymentGatewayConfig

logger = logging.getLogger(__name__)

BREAKERS = {"intasend": intasend_breaker, "daraja": daraja_breaker}


class NoGatewayAvailable(Exception):
    """No enabled gateway is configured (or all are currently unreachable)."""


def _is_configured(provider: str) -> bool:
    if provider == "daraja":
        return daraja.is_configured()
    return bool(getattr(settings, "INTASEND_SECRET_KEY", "") and getattr(settings, "INTASEND_PUBLISHABLE_KEY", ""))


def enabled_providers() -> list[str]:
    """Enabled gateways, primary first (the other only if auto-failover is on)."""
    cfg = PaymentGatewayConfig.load()
    flags = {"intasend": cfg.intasend_enabled, "daraja": cfg.daraja_enabled}
    other = "daraja" if cfg.primary_provider == "intasend" else "intasend"
    order = [cfg.primary_provider] + ([other] if cfg.auto_failover else [])
    return [p for p in order if flags[p]]


def configured_providers() -> list[str]:
    return [p for p in enabled_providers() if _is_configured(p)]


def usable_providers() -> list[str]:
    """Configured gateways whose circuit isn't open right now."""
    return [p for p in configured_providers() if not BREAKERS[p].is_open()]


def _worth_failing_over(exc: Exception) -> bool:
    """
    True only when the gateway clearly never accepted the request (circuit open, can't
    connect, or the gateway answered with an HTTP error such as 5xx/429/bad credentials —
    in each case no prompt was sent). A read timeout is ambiguous — the prompt may
    already be on the phone — so we don't fire a second one from another gateway.
    """
    if isinstance(exc, CircuitOpenError):
        return True
    if isinstance(exc, requests.ConnectionError):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return True
    return False


def initiate_stk(phone_number: str, amount: int, payment_ref: str, email: str = "", narrative: str = "CareerNext") -> tuple[str, str]:
    """
    Send the STK push through the first usable gateway, falling back to the next on a
    clear gateway failure. Returns (provider, checkout_id); raises the last error if
    every gateway failed, or NoGatewayAvailable if none could be tried.
    """
    providers = usable_providers()
    if not providers:
        raise NoGatewayAvailable("No M-Pesa gateway is available")
    last_exc: Exception | None = None
    for provider in providers:
        # services.initiate_stk_push is looked up at call time so it stays patchable.
        send = daraja.initiate_stk_push if provider == "daraja" else services.initiate_stk_push
        try:
            checkout_id = send(
                phone_number=phone_number, amount=amount, payment_ref=payment_ref,
                email=email, narrative=narrative,
            )
            return provider, checkout_id
        except Exception as exc:
            last_exc = exc
            if not _worth_failing_over(exc) and not isinstance(exc, RuntimeError):
                raise
            logger.warning("STK push via %s failed (%s) — trying next gateway", provider, exc)
    raise last_exc  # type: ignore[misc]
