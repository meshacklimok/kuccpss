from django.utils.functional import SimpleLazyObject


def payment_support(request):
    """Support contacts for payment help panels. Lazy: only resolved on pages that use it."""
    from .services import payment_support_contacts
    return {"payment_support": SimpleLazyObject(payment_support_contacts)}
