from django.db import models


class City(models.Model):
    name = models.CharField("نام", max_length=60)
    slug = models.SlugField(unique=True, allow_unicode=True)
    is_active = models.BooleanField("فعال", default=False)  # "به‌زودی" when False
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "شهر"
        verbose_name_plural = "شهرها"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    @classmethod
    def get_current(cls, request):
        slug = request.session.get("city") if hasattr(request, "session") else None
        qs = cls.objects.filter(is_active=True)
        if slug:
            c = qs.filter(slug=slug).first()
            if c:
                return c
        return qs.order_by("order").first()


class District(models.Model):
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="districts", verbose_name="شهر")
    name = models.CharField("نام محله", max_length=60)
    slug = models.SlugField(allow_unicode=True)
    is_active = models.BooleanField("فعال", default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "محله"
        verbose_name_plural = "محله‌ها"
        ordering = ["order", "name"]
        unique_together = [("city", "slug")]

    def __str__(self):
        return self.name


class Category(models.Model):
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children", verbose_name="والد"
    )
    name = models.CharField("نام", max_length=80)
    slug = models.SlugField(unique=True, allow_unicode=True)
    emoji = models.CharField("ایموجی", max_length=8, blank=True)
    color = models.CharField("رنگ پس‌زمینه (CSS)", max_length=40, blank=True, default="var(--amber-100)")
    ph_class = models.CharField("کلاس placeholder", max_length=8, default="ph-a")
    order = models.PositiveSmallIntegerField(default=0)
    safety_tips = models.TextField("نکات ایمنی (هر خط یک مورد، «ایموجی|متن»)", blank=True)
    seo_title = models.CharField(max_length=120, blank=True)
    seo_description = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name if not self.parent else f"{self.parent.name} › {self.name}"

    @property
    def root(self):
        return self.parent or self

    @property
    def full_name(self):
        return str(self)

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("listings:category", args=[self.slug])

    def descendant_ids(self):
        ids = [self.id]
        ids += list(self.children.values_list("id", flat=True))
        return ids

    def tips(self):
        out = []
        for line in (self.safety_tips or self.root.safety_tips or "").splitlines():
            line = line.strip()
            if not line:
                continue
            if "|" in line:
                icon, txt = line.split("|", 1)
            else:
                icon, txt = "•", line
            out.append((icon.strip(), txt.strip()))
        return out


class Brand(models.Model):
    name = models.CharField("نام", max_length=60, unique=True)
    slug = models.SlugField(unique=True, allow_unicode=True)
    order = models.PositiveSmallIntegerField(default=0)
    is_featured = models.BooleanField("نمایش در صفحهٔ اصلی", default=True)

    class Meta:
        verbose_name = "برند"
        verbose_name_plural = "برندها"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class AgeRange(models.TextChoices):
    A0_1 = "0-1", "۰ تا ۱ سال"
    A1_3 = "1-3", "۱ تا ۳ سال"
    A3_5 = "3-5", "۳ تا ۵ سال"
    A5_8 = "5-8", "۵ تا ۸ سال"
    A8P = "8+", "بالای ۸ سال"


AGE_EMOJI = {"0-1": "🍼", "1-3": "🧸", "3-5": "🧩", "5-8": "🧱", "8+": "🎲"}
AGE_SHORT = {"0-1": "۰-۱", "1-3": "۱-۳", "3-5": "۳-۵", "5-8": "۵-۸", "8+": "+۸"}
