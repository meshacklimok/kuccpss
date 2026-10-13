"""
Safaricom Daraja (M-Pesa Express / STK push, Paybill) client.

Kept separate from services.py so the IntaSend code path is untouched. Mirrors its
shapes: initiate_stk_push() returns the checkout id, query_stk() returns
{"state": 'COMPLETE'|'FAILED'|'PENDING', "mpesa_ref": str}.
"""
import base64
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse

from kuccpss.circuit_breaker import daraja_breaker

from .services import normalise_phone

logger = logging.getLogger(__name__)

SANDBOX_BASE = "https://sandbox.safaricom.co.ke"
PROD_BASE = "https://api.safaricom.co.ke"
TOKEN_CACHE_KEY = "daraja:access_token"

# Daraja answers an STK Query for a still-open prompt with HTTP 500 + this code.
STILL_PROCESSING = "500.001.1001"


class Config:
    """Daraja settings: what's saved in admin wins, the DARAJA_* env vars fill any gaps."""

    def __init__(self):
        try:
            from .models import PaymentGatewayConfig
            row = PaymentGatewayConfig.load()
        except Exception:
            row = None

        def pick(field: str, env: str) -> str:
            return ((getattr(row, field, "") or "").strip()) or str(getattr(settings, env, "") or "").strip()

        self.consumer_key = pick("daraja_consumer_key", "DARAJA_CONSUMER_KEY")
        self.consumer_secret = pick("daraja_consumer_secret", "DARAJA_CONSUMER_SECRET")
        self.shortcode = pick("daraja_shortcode", "DARAJA_SHORTCODE")
        self.passkey = pick("daraja_passkey", "DARAJA_PASSKEY")
        self.callback_secret = pick("daraja_callback_secret", "DARAJA_CALLBACK_SECRET")
        self.site_url = (pick("daraja_site_url", "DARAJA_SITE_URL") or "https://www.careernext.co.ke").rstrip("/")
        self.sandbox = bool(getattr(row, "daraja_sandbox", False) or getattr(settings, "DARAJA_SANDBOX", False))

    @property
    def base_url(self) -> str:
        return SANDBOX_BASE if self.sandbox else PROD_BASE

    @property
    def missing(self) -> list[str]:
        labels = {
            "consumer_key": "Consumer key", "consumer_secret": "Consumer secret",
            "shortcode": "Paybill number", "passkey": "Passkey", "callback_secret": "Callback secret",
        }
        return [label for attr, label in labels.items() if not getattr(self, attr)]

    @property
    def callback_url(self) -> str:
        path = reverse("payments:daraja_callback", args=[self.callback_secret or "SECRET"])
        return f"{self.site_url}{path}"


def is_configured() -> bool:
    return not Config().missing


def callback_secret() -> str:
    return Config().callback_secret


def callback_url() -> str:
    return Config().callback_url


def _token_cache_key(cfg: "Config") -> str:
    # Keyed by the credentials, so changing them in admin can never reuse an old token.
    import hashlib
    digest = hashlib.sha256(f"{cfg.consumer_key}:{cfg.consumer_secret}:{cfg.sandbox}".encode()).hexdigest()[:16]
    return f"{TOKEN_CACHE_KEY}:{digest}"


def _fetch_token(cfg: "Config") -> tuple[str, int]:
    response = requests.get(
        f"{cfg.base_url}/oauth/v1/generate",
        params={"grant_type": "client_credentials"},
        auth=(cfg.consumer_key, cfg.consumer_secret),
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    return data["access_token"], int(data.get("expires_in", 3599))


def _access_token(cfg: "Config") -> str:
    key = _token_cache_key(cfg)
    token = cache.get(key)
    if token:
        return token
    token, expires_in = _fetch_token(cfg)
    # Tokens last an hour; refresh a little early.
    cache.set(key, token, max(expires_in - 300, 60))
    return token


def test_connection() -> tuple[bool, str]:
    """Used by admin: do the saved credentials get a token from Safaricom?"""
    cfg = Config()
    if cfg.missing:
        return False, "Missing: " + ", ".join(cfg.missing) + "."
    try:
        token, _ = _fetch_token(cfg)
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "?"
        if code in (400, 401):
            return False, (f"Safaricom rejected the consumer key/secret (HTTP {code}). Check them, and that "
                           f"'Use Safaricom sandbox' matches the kind of credentials you have.")
        return False, f"Safaricom returned HTTP {code}. Try again shortly."
    except requests.RequestException as exc:
        return False, f"Couldn't reach Safaricom ({exc.__class__.__name__}). Try again shortly."
    except (KeyError, ValueError):
        return False, "Safaricom sent an unexpected reply."
    cache.set(_token_cache_key(cfg), token, 3000)
    return True, "Connected to Safaricom Daraja — credentials accepted."


def _stk_credentials(cfg: "Config") -> tuple[str, str]:
    timestamp = datetime.now(ZoneInfo("Africa/Nairobi")).strftime("%Y%m%d%H%M%S")
    raw = f"{cfg.shortcode}{cfg.passkey}{timestamp}"
    return base64.b64encode(raw.encode()).decode(), timestamp


def _post(cfg: "Config", path: str, payload: dict) -> requests.Response:
    """POST with a bearer token. A 401 means a stale cached token: refresh once."""
    for attempt in (1, 2):
        headers = {"Authorization": f"Bearer {_access_token(cfg)}", "Content-Type": "application/json"}
        response = requests.post(f"{cfg.base_url}{path}", json=payload, headers=headers, timeout=15)
        if response.status_code == 401 and attempt == 1:
            cache.delete(_token_cache_key(cfg))
            continue
        return response
    return response  # pragma: no cover


def initiate_stk_push(phone_number: str, amount: int, payment_ref: str, email: str = "", narrative: str = "CareerNext") -> str:
    """
    Fire an M-Pesa STK push to the Paybill. Same signature as services.initiate_stk_push.
    Returns Daraja's CheckoutRequestID; raises requests.HTTPError / RuntimeError on failure.
    """
    cfg = Config()
    password, timestamp = _stk_credentials(cfg)
    payload = {
        "BusinessShortCode": cfg.shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": normalise_phone(phone_number),
        "PartyB": cfg.shortcode,
        "PhoneNumber": normalise_phone(phone_number),
        "CallBackURL": cfg.callback_url,
        "AccountReference": f"CN{payment_ref}"[:12],
        "TransactionDesc": (narrative or "CareerNext")[:20],
    }
    logger.info("Daraja STK push → ref=%s amount=%s", payload["AccountReference"], amount)
    with daraja_breaker.guard():
        response = _post(cfg, "/mpesa/stkpush/v1/processrequest", payload)
        logger.info("Daraja response %s: %s", response.status_code, response.text[:500])
        response.raise_for_status()
    data = response.json()
    if str(data.get("ResponseCode")) != "0" or not data.get("CheckoutRequestID"):
        raise RuntimeError(f"Daraja rejected STK push: {data.get('ResponseDescription') or data}")
    return data["CheckoutRequestID"]


def query_stk(checkout_id: str) -> dict | None:
    """
    Ask Daraja what happened to an STK push. Returns {"state", "mpesa_ref"} or None on
    error. The query never returns the receipt number (only the callback does), so
    mpesa_ref is always blank here.
    """
    if not checkout_id:
        return None
    cfg = Config()
    if cfg.missing:
        return None
    password, timestamp = _stk_credentials(cfg)
    payload = {
        "BusinessShortCode": cfg.shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_id,
    }
    try:
        with daraja_breaker.guard():
            response = _post(cfg, "/mpesa/stkpushquery/v1/query", payload)
            try:
                data = response.json()
            except ValueError:
                data = {}
            if data.get("errorCode") == STILL_PROCESSING:
                return {"state": "PENDING", "mpesa_ref": ""}
            response.raise_for_status()
    except Exception as exc:
        logger.warning("Daraja status query failed for %s: %s", checkout_id, exc)
        return None
    result = data.get("ResultCode")
    if result is None:
        return None
    return {"state": "COMPLETE" if str(result) == "0" else "FAILED", "mpesa_ref": ""}
