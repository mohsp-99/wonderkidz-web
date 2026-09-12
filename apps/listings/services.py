"""Listing lifecycle services: automatic checks, submission under the configured moderation model, expiry."""
import statistics

from django.conf import settings
from django.utils import timezone

from apps.core.text import has_contact_info, normalize

from .models import Listing

BANNED_KEYWORDS = ["صندلی خودرو", "کارسیت", "لباس", "شیر خشک", "پوشک"]


def median_price(category):
    ids = category.descendant_ids() if category.parent_id is None else [category.id]
    prices = list(
        Listing.objects.filter(status=Listing.Status.LIVE, category_id__in=ids, price__isnull=False)
        .exclude(price=0)
        .values_list("price", flat=True)
    )
    if not prices:
        return None
    return int(statistics.median(prices))


def run_auto_checks(listing):
    """Return the automatic-review flags for a listing.

    Each flag: {"code": str, "level": "warn"|"block", "text": str}
    """
    flags = []
    text = f"{listing.title} {listing.description}"

    if has_contact_info(text):
        flags.append({"code": "contact_in_text", "level": "warn", "text": "شماره تماس یا لینک در متن آگهی دیده می‌شود."})

    norm = normalize(text)
    for kw in BANNED_KEYWORDS:
        if normalize(kw) in norm:
            flags.append(
                {"code": "banned_item", "level": "block", "text": f"کالای خارج از حوزهٔ اسباب‌بازی یا ممنوعه: «{kw}»."}
            )
            break

    if listing.price and listing.category_id:
        med = median_price(listing.category)
        if med and listing.price < med * 0.25:
            flags.append(
                {
                    "code": "price_outlier",
                    "level": "warn",
                    "text": f"قیمت بسیار پایین‌تر از میانگین دسته (میانگین {med:,} تومان). الگوی رایج کلاهبرداری «بیعانه بگیر و غیب شو».",
                }
            )

    if not listing.hygiene_note or len(listing.hygiene_note.strip()) < 8:
        flags.append({"code": "hygiene_missing", "level": "warn", "text": "یادداشت بهداشتی خالی یا بسیار کوتاه است."})

    if listing.pk and listing.images.count() <= 1:
        flags.append({"code": "single_image", "level": "warn", "text": "فقط یک عکس دارد."})

    owner = listing.owner
    if owner and (timezone.now() - owner.date_joined).days < 2 and owner.listings.exclude(pk=listing.pk).count() == 0:
        flags.append({"code": "new_account", "level": "warn", "text": "حساب تازه (کمتر از ۲ روز عضویت) و اولین آگهی."})

    return flags


def submit_listing(listing):
    """Apply automatic checks and route the listing according to settings.MODERATION_MODEL."""
    listing.auto_flags = run_auto_checks(listing)
    model = settings.MODERATION_MODEL
    blocked = any(f["level"] == "block" for f in listing.auto_flags)
    if model == "pre_approval" or blocked:
        listing.submit()
    elif model == "post_review":
        listing.submitted_at = timezone.now()
        listing.publish()
    else:  # ai_first
        if listing.auto_flags:
            listing.submit()
        else:
            listing.submitted_at = timezone.now()
            listing.publish()
    return listing


def expire_listings():
    """Move live listings past their expiry date to EXPIRED and clear lapsed promotions. Returns the count."""
    now = timezone.now()
    Listing.objects.filter(is_promoted=True, promoted_until__lt=now).update(is_promoted=False, promoted_until=None)
    return Listing.objects.filter(status=Listing.Status.LIVE, expires_at__lt=now).update(status=Listing.Status.EXPIRED)
