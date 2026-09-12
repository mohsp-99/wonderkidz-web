"""Small factories shared by the test modules."""
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from PIL import Image

from apps.accounts.models import User
from apps.catalog.models import Brand, Category, City, District
from apps.core.images import process_upload
from apps.listings.models import Listing, ListingImage

MEDIA_TMP = tempfile.mkdtemp(prefix="wk-test-media-")

# Every test class that touches images/uploads should be decorated with this.
media_settings = override_settings(
    MEDIA_ROOT=MEDIA_TMP,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
    OTP_DEV_CODE="",
    SMS_BACKEND="console",
    PAYMENT_GATEWAY="fake",
    MODERATION_MODEL="ai_first",
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "wk-tests"}},
)

_counter = {"n": 0}


def _next():
    _counter["n"] += 1
    return _counter["n"]


def make_city(name="تهران", slug="tehran", active=True):
    c, _ = City.objects.get_or_create(slug=slug, defaults={"name": name, "is_active": active})
    return c


def make_district(city=None, name="سعادت‌آباد", slug="saadat-abad"):
    city = city or make_city()
    d, _ = District.objects.get_or_create(city=city, slug=slug, defaults={"name": name})
    return d


def make_category(name="لگو و ساختنی", slug="building", parent=None, **kw):
    c, _ = Category.objects.get_or_create(slug=slug, defaults={"name": name, "parent": parent, "emoji": "🧱", **kw})
    return c


def make_brand(name="LEGO", slug="lego"):
    b, _ = Brand.objects.get_or_create(slug=slug, defaults={"name": name})
    return b


def make_user(phone=None, name="مریم ر.", verified=True, joined_days_ago=30, **kw):
    n = _next()
    phone = phone or f"0912{n:07d}"
    u = User.objects.create_user(phone=phone, display_name=name, is_verified=verified, **kw)
    if joined_days_ago:
        u.date_joined = timezone.now() - timezone.timedelta(days=joined_days_ago)
        u.save(update_fields=["date_joined"])
    return u


def make_staff(phone="09120000000"):
    return User.objects.create_superuser(phone=phone, password="admin", display_name="سمانه ک.")


def make_listing(owner=None, status=Listing.Status.LIVE, category=None, district=None, **kw):
    owner = owner or make_user()
    district = district or make_district()
    category = category or make_category()
    n = _next()
    data = dict(
        owner=owner,
        status=status,
        title=kw.pop("title", f"لگو کلاسیک {n} قطعه با جعبه"),
        category=category,
        age_range=kw.pop("age_range", "5-8"),
        condition=kw.pop("condition", Listing.Condition.LIKE_NEW),
        hygiene_note=kw.pop("hygiene_note", "با آب ولرم و مایع ظرف‌شویی کودک شسته شده است."),
        description=kw.pop("description", "ست لگو کلاسیک که شش ماه دست پسرم بوده و کامل است. جعبه و دفترچه هم هست."),
        price=kw.pop("price", 1_250_000),
        city=district.city,
        district=district,
        attested_safe=True,
    )
    data.update(kw)
    listing = Listing.objects.create(**data)
    if status == Listing.Status.LIVE:
        now = timezone.now()
        listing.published_at = listing.published_at or now
        listing.expires_at = listing.expires_at or now + timezone.timedelta(days=30)
        listing.save()
    return listing


def jpeg_bytes(color=(200, 120, 40), size=(640, 480)):
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG", quality=80)
    return buf.getvalue()


def upload_file(name="a.jpg", color=(200, 120, 40)):
    return SimpleUploadedFile(name, jpeg_bytes(color), content_type="image/jpeg")


def add_image(listing, order=0):
    f = upload_file(f"{listing.code}-{order}.jpg")
    variants, (w, h) = process_upload(f)
    img = ListingImage(listing=listing, order=order, width=w, height=h)
    img.image.save(f"{listing.code}-{order}.webp", variants["gallery"], save=False)
    img.thumb.save(f"{listing.code}-{order}-t.webp", variants["thumb"], save=False)
    img.save()
    return img


def listing_post_data(category, district, **overrides):
    """Valid POST payload for the post-a-listing wizard."""
    data = {
        "type": "sell",
        "category": category.pk,
        "title": "لگو کلاسیک ۵۰۰ قطعه با جعبهٔ اصلی",
        "age_range": "5-8",
        "condition": "likenew",
        "is_complete": "on",
        "has_box": "on",
        "hygiene_note": "با آب ولرم و مایع ظرف‌شویی کودک شسته و کاملاً خشک شده است.",
        "description": "ست لگو کلاسیک ۵۰۰ قطعه که حدود شش ماه دست پسرم بوده. همهٔ قطعات را شمرده‌ام و کامل است.",
        "price": "۱٬۲۵۰٬۰۰۰",
        "original_price": "3400000",
        "is_negotiable": "on",
        "city": district.city.pk,
        "district": district.pk,
        "meetup_hint": "میدان کاج",
        "allow_chat": "on",
        "allow_phone": "on",
        "attested_safe": "on",
    }
    data.update(overrides)
    return data
