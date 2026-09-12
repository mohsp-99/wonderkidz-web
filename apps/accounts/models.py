import random

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.text import clean_phone


class UserManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra):
        phone = clean_phone(phone)
        if not phone:
            raise ValueError("شمارهٔ موبایل معتبر نیست")
        user = self.model(phone=phone, **extra)
        user.set_password(password) if password else user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_verified", True)
        extra.setdefault("display_name", "مدیر")
        return self.create_user(phone, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    class AccountType(models.TextChoices):
        PARENT = "parent", "والد (شخصی)"
        PRO = "pro", "فروشندهٔ حرفه‌ای"
        OFFICIAL = "official", "حساب رسمی وندرکیدز"

    phone = models.CharField("شمارهٔ موبایل", max_length=11, unique=True)
    display_name = models.CharField("نام نمایشی", max_length=60, blank=True)
    account_type = models.CharField("نوع حساب", max_length=10, choices=AccountType.choices, default=AccountType.PARENT)
    city = models.ForeignKey("catalog.City", null=True, blank=True, on_delete=models.SET_NULL, verbose_name="شهر")
    district = models.ForeignKey(
        "catalog.District", null=True, blank=True, on_delete=models.SET_NULL, verbose_name="محلهٔ پیش‌فرض"
    )
    is_verified = models.BooleanField("شمارهٔ تأییدشده", default=False)
    is_active = models.BooleanField("فعال", default=True)
    is_staff = models.BooleanField("دسترسی پنل", default=False)
    is_banned = models.BooleanField("مسدود", default=False)
    ban_reason = models.CharField("دلیل مسدودی", max_length=200, blank=True)
    listing_cap = models.PositiveSmallIntegerField("سقف آگهی فعال", default=settings.NEW_ACCOUNT_LISTING_CAP)
    notify_moderation = models.BooleanField("پیامک نتیجهٔ بررسی", default=True)
    notify_chat = models.BooleanField("پیامک پیام جدید", default=True)
    notify_saved_search = models.BooleanField("پیامک جستجوی ذخیره‌شده", default=False)
    warnings_count = models.PositiveSmallIntegerField("تعداد اخطار", default=0)
    date_joined = models.DateTimeField("تاریخ عضویت", default=timezone.now)
    last_seen = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"

    def __str__(self):
        return self.display_name or self.phone

    @property
    def name(self):
        return self.display_name or "کاربر وندرکیدز"

    @property
    def initial(self):
        return (self.display_name or "و")[0]

    @property
    def is_official(self):
        return self.account_type == self.AccountType.OFFICIAL

    @property
    def is_pro(self):
        return self.account_type == self.AccountType.PRO

    @property
    def active_listing_count(self):
        from apps.listings.models import Listing

        return self.listings.filter(status__in=[Listing.Status.LIVE, Listing.Status.PENDING]).count()

    @property
    def sold_count(self):
        from apps.listings.models import Listing

        return self.listings.filter(status=Listing.Status.SOLD).count()

    def can_post(self):
        return not self.is_banned and self.active_listing_count < self.listing_cap


class OTPCode(models.Model):
    phone = models.CharField(max_length=11, db_index=True)
    code = models.CharField(max_length=8)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used = models.BooleanField(default=False)

    class Meta:
        verbose_name = "کد یک‌بارمصرف"
        verbose_name_plural = "کدهای یک‌بارمصرف"
        ordering = ["-created_at"]

    @classmethod
    def generate(cls, phone):
        code = "".join(random.choices("0123456789", k=settings.OTP_LENGTH))
        return cls.objects.create(
            phone=phone,
            code=code,
            expires_at=timezone.now() + timezone.timedelta(seconds=settings.OTP_TTL_SECONDS),
        )

    @property
    def is_valid(self):
        return not self.used and self.attempts < 5 and timezone.now() < self.expires_at


class SavedSearch(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saved_searches")
    label = models.CharField(max_length=120)
    querystring = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "جستجوی ذخیره‌شده"
        verbose_name_plural = "جستجوهای ذخیره‌شده"

    def __str__(self):
        return self.label
