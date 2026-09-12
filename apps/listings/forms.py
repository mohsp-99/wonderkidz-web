from django import forms
from django.conf import settings

from apps.catalog.models import AgeRange, Brand, Category, City, District
from apps.core.text import has_contact_info, parse_int

from .models import Listing, Report


class ListingForm(forms.ModelForm):
    price = forms.CharField(label="قیمت پیشنهادی شما", required=True)
    original_price = forms.CharField(label="قیمت نو در بازار", required=False)
    attested_safe = forms.BooleanField(
        label="تأیید می‌کنم این کالا سالم، ایمن و فراخوان‌نشده است و عکسی از کودک در آگهی نیست.",
        required=True,
        error_messages={"required": "برای ثبت آگهی باید ایمنی کالا و نبود عکس کودک را تأیید کنید."},
    )

    class Meta:
        model = Listing
        fields = [
            "type", "category", "title", "age_range", "brand", "condition",
            "is_complete", "has_box", "has_manual", "has_battery", "missing_parts",
            "hygiene_note", "description", "price", "original_price", "is_negotiable",
            "city", "district", "meetup_hint", "allow_chat", "allow_phone", "attested_safe",
        ]
        error_messages = {
            "title": {"required": "عنوان آگهی را بنویسید."},
            "category": {"required": "دسته‌بندی را انتخاب کنید."},
            "age_range": {"required": "ردهٔ سنی را انتخاب کنید."},
            "condition": {"required": "وضعیت کالا را انتخاب کنید."},
            "hygiene_note": {"required": "یادداشت بهداشتی برای اسباب‌بازی کودک اجباری است."},
            "description": {"required": "توضیحات را بنویسید."},
            "district": {"required": "محله را انتخاب کنید."},
            "city": {"required": "شهر را انتخاب کنید."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["type"].required = False
        self.fields["city"].queryset = City.objects.filter(is_active=True)
        self.fields["district"].queryset = District.objects.filter(city__is_active=True, is_active=True)
        self.fields["brand"].queryset = Brand.objects.all()
        self.fields["category"].queryset = Category.objects.all()
        self.fields["is_negotiable"].required = False
        self.fields["allow_chat"].required = False
        self.fields["allow_phone"].required = False

    def clean_type(self):
        t = self.cleaned_data.get("type") or Listing.Type.SELL
        if t not in Listing.ENABLED_TYPES:
            raise forms.ValidationError("این نوع آگهی هنوز فعال نشده است.")
        return t

    def clean_title(self):
        t = (self.cleaned_data.get("title") or "").strip()
        if len(t) < 5:
            raise forms.ValidationError("عنوان خیلی کوتاه است.")
        if has_contact_info(t):
            raise forms.ValidationError("از نوشتن شمارهٔ تلفن یا لینک در عنوان خودداری کنید.")
        return t

    def clean_description(self):
        d = (self.cleaned_data.get("description") or "").strip()
        if len(d) < 20:
            raise forms.ValidationError("توضیحات را کمی کامل‌تر بنویسید (حداقل ۲۰ حرف).")
        if has_contact_info(d):
            raise forms.ValidationError("شمارهٔ تماس، لینک شبکه‌های اجتماعی و آدرس دقیق منزل در توضیحات مجاز نیست.")
        return d

    def clean_hygiene_note(self):
        h = (self.cleaned_data.get("hygiene_note") or "").strip()
        if len(h) < 8:
            raise forms.ValidationError("یادداشت بهداشتی را کامل‌تر بنویسید.")
        return h

    def clean_price(self):
        p = parse_int(self.cleaned_data.get("price"))
        if p is None or p <= 0:
            raise forms.ValidationError("قیمت را به تومان وارد کنید.")
        if p > 500_000_000:
            raise forms.ValidationError("قیمت غیرمنطقی است.")
        return p

    def clean_original_price(self):
        raw = self.cleaned_data.get("original_price")
        if not raw:
            return None
        p = parse_int(raw)
        if p is None or p <= 0:
            return None
        return p

    def clean(self):
        data = super().clean()
        city, district = data.get("city"), data.get("district")
        if city and district and district.city_id != city.id:
            self.add_error("district", "محله با شهر انتخاب‌شده نمی‌خواند.")
        if not data.get("allow_chat") and not data.get("allow_phone"):
            self.add_error("allow_chat", "حداقل یکی از راه‌های تماس باید فعال باشد.")
        return data


def validate_images(files, existing_count=0):
    """Return an error string or None."""
    total = existing_count + len(files)
    if total < settings.LISTING_MIN_IMAGES:
        return "حداقل یک عکس لازم است."
    if total > settings.LISTING_MAX_IMAGES:
        return f"حداکثر {settings.LISTING_MAX_IMAGES} عکس می‌توانید بگذارید."
    return None


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["reason", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 3})}


AGE_CHOICES = AgeRange.choices
