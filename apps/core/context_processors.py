from django.conf import settings

from apps.catalog.models import Category, City


def _unread_chat_count(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return 0
    from django.db.models import Q

    from apps.chat.models import Message

    return (
        Message.objects.filter(Q(conversation__buyer=user) | Q(conversation__seller=user), is_read=False)
        .exclude(sender=user)
        .exclude(sender__isnull=True)
        .count()
    )


def site(request):
    return {
        "unread_chat_count": _unread_chat_count(request),
        "SITE_NAME": settings.SITE_NAME,
        "SITE_URL": settings.SITE_URL,
        "CONTACT_PHONE": settings.CONTACT_PHONE,
        "CONTACT_EMAIL": settings.CONTACT_EMAIL,
        "MODERATION_SLA_HOURS": settings.MODERATION_SLA_HOURS,
        "NEW_ACCOUNT_LISTING_CAP": settings.NEW_ACCOUNT_LISTING_CAP,
        "nav_categories": Category.objects.filter(parent__isnull=True).order_by("order")[:12],
        "cities": City.objects.all().order_by("order"),
        "current_city": City.get_current(request),
    }
