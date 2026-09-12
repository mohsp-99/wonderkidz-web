from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import OTPCode, User

from .utils import make_city, make_district, make_user, media_settings


@media_settings
class OTPLoginTests(TestCase):
    def setUp(self):
        cache.clear()
        self.phone = "09123456789"

    def _request_code(self, phone=None):
        r = self.client.post(reverse("accounts:login"), {"phone": phone or self.phone})
        return r

    def test_login_page_renders(self):
        r = self.client.get(reverse("accounts:login"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "ورود یا ثبت‌نام")

    def test_login_post_creates_otp_and_session(self):
        r = self._request_code("۰۹۱۲۳۴۵۶۷۸۹")
        self.assertRedirects(r, reverse("accounts:verify"))
        self.assertEqual(self.client.session["otp_phone"], self.phone)
        otp = OTPCode.objects.get(phone=self.phone)
        self.assertEqual(len(otp.code), 5)
        self.assertTrue(otp.is_valid)
        self.assertEqual(cache.get(f"otp-last:{self.phone}"), otp.code)

    def test_invalid_phone_rejected(self):
        r = self._request_code("12345")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "شمارهٔ موبایل معتبر نیست")
        self.assertFalse(OTPCode.objects.exists())

    def test_verify_without_session_redirects(self):
        r = self.client.get(reverse("accounts:verify"))
        self.assertRedirects(r, reverse("accounts:login"))

    def test_wrong_code_increments_attempts(self):
        self._request_code()
        r = self.client.post(reverse("accounts:verify"), {"code": "00000"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "کد وارد شده درست نیست")
        self.assertEqual(OTPCode.objects.get(phone=self.phone).attempts, 1)
        self.assertFalse(User.objects.filter(phone=self.phone).exists())

    def test_correct_code_logs_in_and_creates_verified_user(self):
        self._request_code()
        code = cache.get(f"otp-last:{self.phone}")
        r = self.client.post(reverse("accounts:verify"), {"code": code})
        self.assertRedirects(r, reverse("accounts:profile"))
        user = User.objects.get(phone=self.phone)
        self.assertTrue(user.is_verified)
        self.assertTrue(OTPCode.objects.get(phone=self.phone).used)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertNotIn("otp_phone", self.client.session)

    def test_persian_digit_code_accepted(self):
        self._request_code()
        code = cache.get(f"otp-last:{self.phone}")
        fa = code.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
        r = self.client.post(reverse("accounts:verify"), {"code": fa})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(phone=self.phone).exists())

    def test_next_is_respected(self):
        self._request_code()
        self.client.get(reverse("accounts:login") + "?next=/new/")  # stores next in session
        code = cache.get(f"otp-last:{self.phone}")
        r = self.client.post(reverse("accounts:verify"), {"code": code})
        self.assertRedirects(r, "/new/", fetch_redirect_response=False)

    def test_unsafe_next_ignored(self):
        self._request_code()
        code = cache.get(f"otp-last:{self.phone}")
        r = self.client.post(reverse("accounts:verify"), {"code": code, "next": "https://evil.example/x"})
        self.assertRedirects(r, reverse("accounts:profile"))

    @override_settings(OTP_DEV_CODE="12345")
    def test_dev_code_accepted(self):
        self._request_code()
        r = self.client.post(reverse("accounts:verify"), {"code": "12345"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(phone=self.phone, is_verified=True).exists())

    def test_expired_code_rejected(self):
        self._request_code()
        otp = OTPCode.objects.get(phone=self.phone)
        otp.expires_at = otp.created_at - otp.created_at.resolution  # in the past
        otp.save()
        r = self.client.post(reverse("accounts:verify"), {"code": otp.code})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "کد منقضی شده است")

    def test_rate_limit(self):
        for _ in range(5):
            self.assertEqual(self._request_code().status_code, 302)
        r = self.client.post(reverse("accounts:login"), {"phone": self.phone}, follow=True)
        self.assertContains(r, "بیش از حد مجاز")
        self.assertEqual(OTPCode.objects.filter(phone=self.phone).count(), 5)

    def test_resend_issues_new_code(self):
        self._request_code()
        first = cache.get(f"otp-last:{self.phone}")
        r = self.client.post(reverse("accounts:resend"))
        self.assertRedirects(r, reverse("accounts:verify"))
        self.assertEqual(OTPCode.objects.filter(phone=self.phone).count(), 2)
        self.assertEqual(OTPCode.objects.filter(phone=self.phone, used=False).count(), 1)
        # verifying with the superseded code fails
        r = self.client.post(reverse("accounts:verify"), {"code": first})
        self.assertEqual(r.status_code, 200)

    def test_banned_user_refused(self):
        make_user(phone=self.phone, is_banned=True, ban_reason="اسپم")
        self._request_code()
        code = cache.get(f"otp-last:{self.phone}")
        r = self.client.post(reverse("accounts:verify"), {"code": code}, follow=True)
        self.assertContains(r, "این حساب مسدود شده است")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout(self):
        u = make_user()
        self.client.force_login(u)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        r = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(r, reverse("listings:home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_authenticated_user_skips_login(self):
        self.client.force_login(make_user())
        r = self.client.get(reverse("accounts:login"))
        self.assertRedirects(r, reverse("accounts:profile"))


@media_settings
class ProfileTests(TestCase):
    def setUp(self):
        cache.clear()
        self.city = make_city()
        self.district = make_district(self.city)
        self.user = make_user(name="مریم ر.", city=self.city, district=self.district)

    def test_profile_requires_login(self):
        r = self.client.get(reverse("accounts:profile"))
        self.assertRedirects(r, f"{reverse('accounts:login')}?next={reverse('accounts:profile')}")

    def test_profile_renders(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("accounts:profile"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "مریم ر.")
        self.assertContains(r, "آگهی‌های فعال")

    def test_account_edit_saves(self):
        self.client.force_login(self.user)
        r = self.client.post(
            reverse("accounts:account_edit"),
            {"display_name": "مریم رضایی", "city": self.city.pk, "district": self.district.pk, "notify_chat": "on"},
        )
        self.assertEqual(r.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.display_name, "مریم رضایی")
        self.assertTrue(self.user.notify_chat)
        self.assertFalse(self.user.notify_moderation)
        self.assertEqual(self.user.district, self.district)

    def test_account_edit_rejects_district_of_other_city(self):
        other = make_city("کرج", "karaj")
        d2 = make_district(other, "گوهردشت", "gohardasht")
        self.client.force_login(self.user)
        self.client.post(reverse("accounts:account_edit"), {"city": self.city.pk, "district": d2.pk})
        self.user.refresh_from_db()
        self.assertEqual(self.user.district, self.district)

    def test_account_edit_get_not_allowed(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:account_edit")).status_code, 405)

    def test_set_city(self):
        make_city("کرج", "karaj", active=False)
        r = self.client.post(reverse("accounts:set_city"), {"city": "tehran"})
        self.assertRedirects(r, reverse("listings:home"))
        self.assertEqual(self.client.session["city"], "tehran")
        self.client.post(reverse("accounts:set_city"), {"city": "karaj"})  # inactive: ignored
        self.assertEqual(self.client.session["city"], "tehran")

    def test_public_profile(self):
        r = self.client.get(reverse("accounts:public_profile", args=[self.user.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "مریم ر.")
        self.assertEqual(self.client.get(reverse("accounts:public_profile", args=[9999])).status_code, 404)

    def test_saved_search_delete(self):
        from apps.accounts.models import SavedSearch

        ss = SavedSearch.objects.create(user=self.user, label="لگو", querystring="q=لگو")
        other = make_user()
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse("accounts:saved_search_delete", args=[ss.pk])).status_code, 404)
        self.client.force_login(self.user)
        self.client.post(reverse("accounts:saved_search_delete", args=[ss.pk]))
        self.assertFalse(SavedSearch.objects.filter(pk=ss.pk).exists())


class UserModelTests(TestCase):
    def test_create_user_normalizes_phone(self):
        u = User.objects.create_user("+98 912 345 6789")
        self.assertEqual(u.phone, "09123456789")
        self.assertFalse(u.has_usable_password())
        with self.assertRaises(ValueError):
            User.objects.create_user("123")

    def test_superuser(self):
        u = User.objects.create_superuser("09120000000", "admin")
        self.assertTrue(u.is_staff and u.is_superuser and u.is_verified)
        self.assertTrue(u.check_password("admin"))

    def test_can_post_cap(self):
        u = make_user(listing_cap=1)
        self.assertTrue(u.can_post())
        from .utils import make_listing

        make_listing(owner=u)
        self.assertFalse(u.can_post())
        u.is_banned = True
        self.assertFalse(u.can_post())


class SmsBackendTests(TestCase):
    def test_console_backend(self):
        from apps.accounts import sms

        cache.clear()
        self.assertTrue(sms.send_otp("09123456789", "12345"))
        self.assertEqual(cache.get("otp-last:09123456789"), "12345")
        self.assertTrue(sms.send_sms("09123456789", "سلام"))

    @override_settings(SMS_BACKEND="kavenegar", KAVENEGAR_API_KEY="k")
    def test_kavenegar_backend_mocked(self):
        from unittest import mock

        from apps.accounts import sms

        self.assertIsInstance(sms.get_backend(), sms.KavenegarBackend)
        resp = mock.Mock()
        resp.json.return_value = {"return": {"status": 200}}
        with mock.patch("apps.accounts.sms.requests.post", return_value=resp) as post:
            self.assertTrue(sms.send_otp("09123456789", "12345"))
            self.assertIn("verify/lookup.json", post.call_args[0][0])
            self.assertEqual(post.call_args[1]["data"]["token"], "12345")
        with mock.patch("apps.accounts.sms.requests.post", side_effect=OSError("down")):
            self.assertFalse(sms.send_otp("09123456789", "12345"))  # never raises

    @override_settings(SMS_BACKEND="smsir", SMSIR_API_KEY="k", SMSIR_OTP_TEMPLATE_ID=7)
    def test_smsir_backend_mocked(self):
        from unittest import mock

        from apps.accounts import sms

        resp = mock.Mock()
        resp.json.return_value = {"status": 1}
        with mock.patch("apps.accounts.sms.requests.post", return_value=resp) as post:
            self.assertTrue(sms.send_otp("09123456789", "12345"))
            self.assertEqual(post.call_args[1]["json"]["templateId"], 7)
            self.assertEqual(post.call_args[1]["headers"]["x-api-key"], "k")
