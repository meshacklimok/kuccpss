from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='accounts.User')
def on_user_created(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from .models import EventLog
        EventLog.objects.create(
            name='user_registered',
            properties={
                'auth_method': 'google' if instance.is_google_user else 'email',
            },
            user=instance,
        )
        _posthog(str(instance.pk), 'user_registered', {
            'auth_method': 'google' if instance.is_google_user else 'email',
        })
    except Exception:
        pass


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


def _posthog(distinct_id, event, properties):
    try:
        from .utils import track_posthog
        track_posthog(distinct_id, event, properties)
    except Exception:
        pass
