from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


# ── Registration ──────────────────────────────────────────────────────────────

@receiver(post_save, sender='accounts.User')
def on_user_created(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from .models import EventLog
        EventLog.objects.create(
            name='user_registered',
            properties={'auth_method': 'google' if instance.is_google_user else 'email'},
            user=instance,
        )
        _posthog(str(instance.pk), 'user_registered', {
            'auth_method': 'google' if instance.is_google_user else 'email',
        })
    except Exception:
        pass


# ── Payments ──────────────────────────────────────────────────────────────────

@receiver(post_save, sender='payments.Payment')
def on_payment_saved(sender, instance, created, **kwargs):
    try:
        from .models import EventLog
        name = 'payment_initiated' if created else f'payment_{instance.status}'
        EventLog.objects.create(
            name=name,
            properties={
                'feature': instance.feature,
                'amount':  float(instance.amount),
                'status':  instance.status,
            },
            user=instance.user,
        )
        if instance.status == 'completed':
            _posthog(str(instance.user_id), 'payment_completed', {
                'feature': instance.feature,
                'amount':  float(instance.amount),
                'currency': 'KES',
            })
    except Exception:
        pass


# ── Login / Logout ────────────────────────────────────────────────────────────

@receiver(user_logged_in)
def on_user_login(sender, request, user, **kwargs):
    try:
        from .models import UserActionLog
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        ip  = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')
        sk  = ''
        try:
            sk = request.session.session_key or ''
        except Exception:
            pass
        UserActionLog.objects.create(
            action='login',
            properties={'auth_method': 'google' if getattr(user, 'is_google_user', False) else 'email'},
            user=user,
            session_key=sk,
            ip=ip or None,
        )
    except Exception:
        pass


@receiver(user_logged_out)
def on_user_logout(sender, request, user, **kwargs):
    try:
        from .models import UserActionLog
        if not user:
            return
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        ip  = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')
        UserActionLog.objects.create(
            action='logout',
            properties={},
            user=user,
            session_key='',
            ip=ip or None,
        )
    except Exception:
        pass


# ── Shortlist (SavedCourse) ───────────────────────────────────────────────────

@receiver(post_save, sender='accounts.SavedCourse')
def on_shortlist_add(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from .models import UserActionLog
        UserActionLog.objects.create(
            action='shortlist_add',
            properties={'course': str(instance.course)},
            user=instance.user,
        )
    except Exception:
        pass


@receiver(post_delete, sender='accounts.SavedCourse')
def on_shortlist_remove(sender, instance, **kwargs):
    try:
        from .models import UserActionLog
        UserActionLog.objects.create(
            action='shortlist_remove',
            properties={'course': str(instance.course)},
            user=instance.user,
        )
    except Exception:
        pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _posthog(distinct_id, event, properties):
    try:
        from .utils import track_posthog
        track_posthog(distinct_id, event, properties)
    except Exception:
        pass
