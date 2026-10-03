"""
Audit trail helper. Call record() wherever money moves or a privileged action
happens outside the Django admin's own LogEntry history.

record() never raises: an audit write failing must not roll back or break the
payment/payout it describes. Failures are logged at ERROR so Sentry sees them.
"""
import logging

from django.db import transaction

logger = logging.getLogger(__name__)


def record(action, target=None, *, actor=None, request=None, amount=None, **details):
    from .models import AuditLog

    try:
        if actor is None and request is not None:
            user = getattr(request, 'user', None)
            actor = user if getattr(user, 'is_authenticated', False) else None
        ip = None
        if request is not None:
            from kuccpss.ip_utils import get_client_ip
            ip = get_client_ip(request) or None
        # Savepoint: if the insert fails inside a caller's atomic() block, only
        # the audit row is rolled back, not the money movement it describes.
        with transaction.atomic():
            return AuditLog.objects.create(
                action=action,
                actor=actor,
                actor_label=getattr(actor, 'email', '') or ('system' if actor is None else str(actor)),
                target_type=target._meta.label_lower if target is not None else '',
                target_id=str(target.pk) if target is not None else '',
                amount=amount,
                details={k: _jsonable(v) for k, v in details.items()},
                ip=ip,
            )
    except Exception:
        logger.exception("Audit log write failed for action=%s", action)
        return None


def _jsonable(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
