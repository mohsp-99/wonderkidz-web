import random

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import AgeRange
from apps.core.text import normalize


def _code():
    return str(random.randint(100000, 999999))


class Listing(models.Model):
    class Type(models.TextChoices):
        SELL = "sell", "فروش"
        FREE = "free", "رایگان"
        DONATE = "donate", "اهدا به خیریه"
        WANTED = "wanted", "دنبالش می‌گردم"
        SWAP = "swap", "معاوضه"
        RENT = "rent", "اجارهٔ نفر به نفر"

    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        PENDING = "pending", "در انتظار تأیید"
        LIVE = "live", "منتشر شده"
        REJECTED = "rejected", "رد شد"
        PAUSED = "paused", "متوقف"
        SOLD = "sold", "فروخته شد"
        EXPIRED = "expired", "منقضی"
        REMOVED = "removed", "حذف‌شده"

    class Condition(models.TextChoices):
        NEW = "new", "نو"
        LIKE_NEW = "likenew", "در حد نو"
        USED = "used", "کارکردهٔ سالم"
        REPAIR = "repair", "نیاز به تعمیر"

    ENABLED_TYPES = [Type.SELL]  # UI ships sell-only; schema carries the full set.

    code = models.CharField("کد آگهی", max_length=8, unique=True, default=_code)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="listings", verbose_name="فروشنده")
    type = models.CharField("نوع آگهی", max_length=10, choices=Type.choices, default=Type.SELL)
    status = models.CharField("وضعیت", max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)

    title = models.CharField("عنوان", max_length=90)
    slug = models.SlugField(max_length=120, allow_unicode=True, blank=True)
    category = models.ForeignKey("catalog.Category", on_delete=models.PROTECT, related_name="listings", verbose_name="دسته‌بندی")
    brand = models.ForeignKey("catalog.Brand", null=True, blank=True, on_delete=models.SET_NULL, verbose_name="برند")
    age_range = models.CharField("ردهٔ سنی", max_length=4, choices=AgeRange.choices)
    condition = models.CharField("وضعیت کالا", max_length=8, choices=Condition.choices)
    is_complete = models.BooleanField("همهٔ قطعات موجود", default=True)
    has_box = models.BooleanField("جعبهٔ اصلی", default=False)
    has_manual = models.BooleanField("دفترچهٔ راهنما", default=False)
    has_battery = models.BooleanField("باتری/شارژر همراه", default=False)
    missing_parts = models.BooleanField("چند قطعه کم دارد", default=False)
    hygiene_note = models.CharField("یادداشت بهداشتی", max_length=200)
    description = models.TextField("توضیحات")
    attributes = models.JSONField("مشخصات تکمیلی", default=dict, blank=True)

    price = models.PositiveBigIntegerField("قیمت (تومان)", null=True, blank=True)
    original_price = models.PositiveBigIntegerField("قیمت نو (تومان)", null=True, blank=True)
    is_negotiable = models.BooleanField("قابل مذاکره", default=True)

    city = models.ForeignKey("catalog.City", on_delete=models.PROTECT, verbose_name="شهر")
    district = models.ForeignKey("catalog.District", on_delete=models.PROTECT, verbose_name="محله")
    meetup_hint = models.CharField("محل پیشنهادی تحویل", max_length=120, blank=True)
    allow_chat = models.BooleanField("چت فعال", default=True)
    allow_phone = models.BooleanField("نمایش شماره", default=True)
    attested_safe = models.BooleanField("تأیید ایمنی و بدون عکس کودک", default=False)

    is_promoted = models.BooleanField("نردبان/ویژه", default=False)
    promoted_until = models.DateTimeField(null=True, blank=True)

    views_count = models.PositiveIntegerField("بازدید", default=0)
    reveals_count = models.PositiveIntegerField("نمایش شماره", default=0)
    search_text = models.TextField(blank=True, editable=False)

    # moderation
    auto_flags = models.JSONField("هشدارهای خودکار", default=list, blank=True)
    reject_reason = models.CharField("دلیل رد", max_length=200, blank=True)
    reject_note = models.TextField("توضیح رد", blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField("زمان ارسال برای بررسی", null=True, blank=True)
    published_at = models.DateTimeField("زمان انتشار", null=True, blank=True)
    expires_at = models.DateTimeField("انقضا", null=True, blank=True)
    sold_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "آگهی"
        verbose_name_plural = "آگهی‌ها"
        ordering = ["-published_at", "-created_at"]
        indexes = [models.Index(fields=["status", "city", "category"]), models.Index(fields=["status", "published_at"])]

    def __str__(self):
        return self.title

    # ---- urls ----
    def get_absolute_url(self):
        return reverse("listings:detail", args=[self.code, self.slug or "agahi"])

    # ---- derived ----
    @property
    def is_live(self):
        return self.status == self.Status.LIVE

    @property
    def cover(self):
        return self.images.order_by("order").first()

    @property
    def image_count(self):
        return self.images.count()

    @property
    def percent_off(self):
        if self.price and self.original_price and self.original_price > self.price:
            return round((1 - self.price / self.original_price) * 100)
        return None

    @property
    def is_expiring_soon(self):
        return self.expires_at and (self.expires_at - timezone.now()).days <= 14

    @property
    def condition_badge(self):
        return {"new": "badge-new", "likenew": "badge-likenew", "used": "badge-used", "repair": "badge-repair"}[self.condition]

    @property
    def completeness_text(self):
        if self.missing_parts:
            return "چند قطعه کم دارد"
        parts = []
        if self.is_complete:
            parts.append("همهٔ قطعات موجود")
        if self.has_box:
            parts.append("جعبه")
        if self.has_manual:
            parts.append("دفترچه")
        return "، ".join(parts) if parts else "—"

    @property
    def ph_class(self):
        return self.category.ph_class or "ph-a"

    @property
    def emoji(self):
        return self.category.emoji or "🧸"

    # ---- lifecycle ----
    def refresh_search_text(self):
        bits = [self.title, self.description, self.category.name, self.category.root.name, self.district.name]
        if self.brand:
            bits.append(self.brand.name)
        self.search_text = normalize(" ".join(b for b in bits if b))

    def save(self, *args, **kwargs):
        from django.utils.text import slugify

        if not self.slug:
            self.slug = slugify(self.title, allow_unicode=True)[:110] or "agahi"
        if self.category_id and self.district_id:
            self.refresh_search_text()
        super().save(*args, **kwargs)

    def submit(self):
        self.status = self.Status.PENDING
        self.submitted_at = timezone.now()
        self.reject_reason = ""
        self.reject_note = ""
        self.save()

    def publish(self, by=None):
        now = timezone.now()
        self.status = self.Status.LIVE
        self.published_at = self.published_at or now
        self.expires_at = now + timezone.timedelta(days=settings.LISTING_TTL_DAYS)
        self.reviewed_by = by
        self.reviewed_at = now
        self.save()

    def reject(self, reason, note="", by=None):
        self.status = self.Status.REJECTED
        self.reject_reason = reason
        self.reject_note = note
        self.reviewed_by = by
        self.reviewed_at = timezone.now()
        self.save()

    def mark_sold(self):
        self.status = self.Status.SOLD
        self.sold_at = timezone.now()
        self.save()

    def renew(self):
        self.expires_at = timezone.now() + timezone.timedelta(days=settings.LISTING_TTL_DAYS)
        if self.status == self.Status.EXPIRED:
            self.status = self.Status.LIVE
        self.save()


class ListingImage(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField("عکس (گالری)", upload_to="listings/%Y/%m/")
    thumb = models.ImageField("بندانگشتی", upload_to="listings/%Y/%m/thumbs/", blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "عکس آگهی"
        verbose_name_plural = "عکس‌های آگهی"

    @property
    def thumb_url(self):
        return self.thumb.url if self.thumb else self.image.url


class SavedListing(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved")
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="saved_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "listing")]
        verbose_name = "آگهی ذخیره‌شده"
        verbose_name_plural = "آگهی‌های ذخیره‌شده"


class PhoneReveal(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="reveals")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="phone_reveals")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "نمایش شماره"
        verbose_name_plural = "نمایش‌های شماره"


class Report(models.Model):
    class Reason(models.TextChoices):
        SCAM = "scam", "مشکوک به کلاهبرداری (درخواست بیعانه)"
        MISMATCH = "mismatch", "وضعیت واقعی با آگهی نمی‌خواند"
        PROHIBITED = "prohibited", "کالای ممنوعه یا ناایمن"
        CHILD_PHOTO = "child_photo", "عکس کودک در آگهی"
        ABUSE = "abuse", "پیام توهین‌آمیز"
        SPAM = "spam", "اسپم / تکراری"
        OTHER = "other", "موارد دیگر"

    class Status(models.TextChoices):
        OPEN = "open", "باز"
        RESOLVED = "resolved", "رسیدگی شد"
        DISMISSED = "dismissed", "بی‌اشکال"

    class Priority(models.TextChoices):
        URGENT = "urgent", "فوری"
        NORMAL = "normal", "متوسط"
        LOW = "low", "کم"

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports")
    listing = models.ForeignKey(Listing, null=True, blank=True, on_delete=models.CASCADE, related_name="reports")
    conversation = models.ForeignKey("chat.Conversation", null=True, blank=True, on_delete=models.CASCADE, related_name="reports")
    reason = models.CharField("نوع گزارش", max_length=20, choices=Reason.choices)
    note = models.TextField("توضیح", blank=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    resolution = models.CharField("اقدام", max_length=200, blank=True)
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    handled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "گزارش"
        verbose_name_plural = "گزارش‌ها"
        ordering = ["-created_at"]

    @property
    def target_title(self):
        if self.listing_id:
            return self.listing.title
        return f"گفت‌وگو #{self.conversation_id}"
