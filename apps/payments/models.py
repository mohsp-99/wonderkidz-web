from django.conf import settings
from django.db import models


class Plan(models.Model):
    """Dormant at launch: fee is off, but the schema is ready so it can be switched on without migration."""

    class Kind(models.TextChoices):
        PROMOTE = "promote", "نردبان / آگهی ویژه"
        SUBSCRIPTION = "subscription", "اشتراک فروشنده"
        BADGE = "badge", "نشان فروشنده"

    name = models.CharField("نام", max_length=80)
    kind = models.CharField(max_length=15, choices=Kind.choices)
    price = models.PositiveBigIntegerField("قیمت (تومان)")
    duration_days = models.PositiveSmallIntegerField("مدت (روز)", default=7)
    description = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField("فعال", default=False)

    class Meta:
        verbose_name = "پلن"
        verbose_name_plural = "پلن‌ها"

    def __str__(self):
        return self.name


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        PAID = "paid", "پرداخت شد"
        FAILED = "failed", "ناموفق"
        CANCELED = "canceled", "لغو شد"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    listing = models.ForeignKey("listings.Listing", null=True, blank=True, on_delete=models.SET_NULL, related_name="payments")
    amount = models.PositiveBigIntegerField("مبلغ (تومان)")
    gateway = models.CharField(max_length=20)
    authority = models.CharField("شناسهٔ درگاه", max_length=100, blank=True, db_index=True)
    ref_id = models.CharField("کد پیگیری", max_length=100, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "پرداخت"
        verbose_name_plural = "پرداخت‌ها"

    def __str__(self):
        return f"{self.user} — {self.plan} — {self.get_status_display()}"
