from django.template import Context, Template
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.core import dates, text


class TextHelpersTests(SimpleTestCase):
    def test_digits(self):
        self.assertEqual(text.to_en_digits("۰۹۱۲۳۴۵۶۷۸۹"), "09123456789")
        self.assertEqual(text.to_en_digits("٠٩١٢"), "0912")
        self.assertEqual(text.to_fa_digits(1405), "۱۴۰۵")

    def test_normalize_unifies_arabic_letters_and_digits(self):
        self.assertEqual(text.normalize("كتاب"), text.normalize("کتاب"))
        self.assertEqual(text.normalize("بازي"), text.normalize("بازی"))
        self.assertEqual(text.normalize("  LEGO  ۵۰۰ "), "lego 500")
        self.assertEqual(text.normalize("می‌خواهم"), "می خواهم")
        self.assertEqual(text.normalize(""), "")

    def test_parse_int(self):
        self.assertEqual(text.parse_int("۱٬۲۵۰٬۰۰۰"), 1_250_000)
        self.assertEqual(text.parse_int("1,250,000"), 1_250_000)
        self.assertEqual(text.parse_int("abc"), None)
        self.assertEqual(text.parse_int(None, 7), 7)

    def test_format_price(self):
        self.assertEqual(text.format_price(1250000), "۱٬۲۵۰٬۰۰۰")
        self.assertEqual(text.format_price(None), "")

    def test_clean_phone_variants(self):
        for raw in ("09123456789", "۰۹۱۲۳۴۵۶۷۸۹", "+989123456789", "00989123456789", "989123456789", "9123456789", "0912 345 6789"):
            self.assertEqual(text.clean_phone(raw), "09123456789", raw)
        for bad in ("0812345678", "12345", "", None, "0912345678"):
            self.assertIsNone(text.clean_phone(bad), bad)

    def test_mask_phone(self):
        self.assertEqual(text.mask_phone("09123456789"), "۰۹۱۲ ۳۴۵ ۶۷۸۹")

    def test_has_contact_info(self):
        self.assertTrue(text.has_contact_info("تماس 09123456789"))
        self.assertTrue(text.has_contact_info("شماره ۰۹۱۲ ۳۴۵ ۶۷۸۹"))
        self.assertTrue(text.has_contact_info("https://example.com"))
        self.assertTrue(text.has_contact_info("پیج اینستاگرام ما"))
        self.assertTrue(text.has_contact_info("t.me/foo"))
        self.assertFalse(text.has_contact_info("لگو کلاسیک ۵۰۰ قطعه با جعبه"))


class DatesTests(SimpleTestCase):
    def test_ago_strings(self):
        now = timezone.now()
        self.assertEqual(dates.ago(now), "هم‌اکنون")
        self.assertEqual(dates.ago(now - timezone.timedelta(minutes=5)), "۵ دقیقه پیش")
        self.assertEqual(dates.ago(now - timezone.timedelta(hours=2)), "۲ ساعت پیش")
        self.assertEqual(dates.ago(now - timezone.timedelta(days=1, hours=1)), "دیروز")
        self.assertEqual(dates.ago(now - timezone.timedelta(days=3)), "۳ روز پیش")
        self.assertEqual(dates.ago(now - timezone.timedelta(days=21)), "۳ هفته پیش")
        self.assertEqual(dates.ago(None), "")

    def test_jalali(self):
        # 2026-09-12 = 1405/06/21
        dt = timezone.make_aware(timezone.datetime(2026, 9, 12, 12, 0))
        self.assertEqual(dates.jalali(dt), "۲۱ شهریور ۱۴۰۵")
        self.assertEqual(dates.jalali_month_year(dt), "شهریور ۱۴۰۵")
        self.assertEqual(dates.jalali_year(dt), "۱۴۰۵")

    def test_days_left(self):
        self.assertEqual(dates.days_left(timezone.now() + timezone.timedelta(days=11, hours=1)), 11)
        self.assertEqual(dates.days_left(timezone.now() - timezone.timedelta(days=1)), 0)


class TemplateFilterTests(TestCase):
    def render(self, tpl, **ctx):
        return Template(tpl).render(Context(ctx))

    def test_filters(self):
        self.assertEqual(self.render("{{ n|fa }}", n=243), "۲۴۳")
        self.assertEqual(self.render("{{ p|price }}", p=95000), "۹۵٬۰۰۰")
        self.assertEqual(self.render("{{ ph|phone }}", ph="09128890878"), "۰۹۱۲ ۸۸۹ ۰۸۷۸")
        self.assertEqual(self.render("{{ d|ago }}", d=timezone.now()), "هم‌اکنون")
        self.assertEqual(self.render("{% jalali_year %}"), dates.jalali_year())

    def test_qs_tags(self):
        from django.test import RequestFactory

        req = RequestFactory().get("/s/?age=3-5&cond=new&page=3")
        out = self.render("{% qs_toggle 'age' '1-3' %}", request=req)
        self.assertIn("age=3-5", out)
        self.assertIn("age=1-3", out)
        self.assertNotIn("page=", out)
        out = self.render("{% qs_toggle 'age' '3-5' %}", request=req)
        self.assertNotIn("age=3-5", out)
        out = self.render("{% qs_replace cond='' sort='cheapest' %}", request=req)
        self.assertNotIn("cond=", out)
        self.assertIn("sort=cheapest", out)
