from unittest import mock

from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.payments import gateways
from apps.payments.models import Payment, Plan

from .utils import make_listing, make_user, media_settings


@media_settings
class FakeGatewayFlowTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.listing = make_listing(owner=self.user)
        self.plan = Plan.objects.create(name="نردبان ۷ روزه", kind=Plan.Kind.PROMOTE, price=49000, duration_days=7, is_active=True)
        Plan.objects.create(name="غیرفعال", kind=Plan.Kind.BADGE, price=1000, is_active=False)
        self.client.force_login(self.user)

    def test_plans_page(self):
        r = self.client.get(reverse("payments:plans") + f"?listing={self.listing.code}")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "نردبان ۷ روزه")
        self.assertNotContains(r, "غیرفعال")

    def test_plans_page_without_active_plans(self):
        Plan.objects.update(is_active=False)
        r = self.client.get(reverse("payments:plans"))
        self.assertContains(r, "هیچ هزینه‌ای")

    def test_plans_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("payments:plans")).status_code, 302)

    def test_inactive_plan_cannot_start(self):
        inactive = Plan.objects.get(name="غیرفعال")
        self.assertEqual(self.client.post(reverse("payments:start", args=[inactive.pk])).status_code, 404)

    def test_end_to_end_success_promotes_listing(self):
        r = self.client.post(reverse("payments:start", args=[self.plan.pk]), {"listing": self.listing.code})
        payment = Payment.objects.get()
        self.assertEqual(payment.amount, 49000)
        self.assertEqual(payment.gateway, "fake")
        self.assertEqual(payment.listing, self.listing)
        self.assertTrue(payment.authority.startswith("FAKE-"))
        self.assertRedirects(r, reverse("payments:fake_gateway", args=[payment.pk]))
        r = self.client.get(reverse("payments:fake_gateway", args=[payment.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "۴۹٬۰۰۰")
        r = self.client.get(reverse("payments:callback") + f"?payment={payment.pk}&status=ok")
        self.assertRedirects(r, reverse("payments:result", args=[payment.pk]))
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertEqual(payment.ref_id, f"FAKE{payment.pk:08d}")
        self.assertIsNotNone(payment.paid_at)
        self.listing.refresh_from_db()
        self.assertTrue(self.listing.is_promoted)
        self.assertIsNotNone(self.listing.promoted_until)
        r = self.client.get(reverse("payments:result", args=[payment.pk]))
        self.assertContains(r, payment.ref_id)
        # callback is idempotent
        self.client.get(reverse("payments:callback") + f"?payment={payment.pk}&status=cancel")
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)

    def test_cancel_path(self):
        self.client.post(reverse("payments:start", args=[self.plan.pk]))
        payment = Payment.objects.get()
        self.client.get(reverse("payments:callback") + f"?payment={payment.pk}&status=cancel")
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.CANCELED)
        self.listing.refresh_from_db()
        self.assertFalse(self.listing.is_promoted)

    def test_subscription_and_badge_effects(self):
        sub = Plan.objects.create(name="اشتراک", kind=Plan.Kind.SUBSCRIPTION, price=290000, is_active=True)
        badge = Plan.objects.create(name="نشان", kind=Plan.Kind.BADGE, price=90000, is_active=True)
        cap = self.user.listing_cap
        for plan in (sub, badge):
            self.client.post(reverse("payments:start", args=[plan.pk]))
            p = Payment.objects.filter(plan=plan).get()
            self.client.get(reverse("payments:callback") + f"?payment={p.pk}&status=ok")
        self.user.refresh_from_db()
        self.assertEqual(self.user.listing_cap, cap + 20)
        self.assertEqual(self.user.account_type, self.user.AccountType.PRO)

    def test_callback_unknown_payment_404(self):
        self.assertEqual(self.client.get(reverse("payments:callback") + "?payment=999").status_code, 404)
        self.assertEqual(self.client.get(reverse("payments:callback")).status_code, 404)

    def test_result_is_owner_only(self):
        self.client.post(reverse("payments:start", args=[self.plan.pk]))
        payment = Payment.objects.get()
        self.client.force_login(make_user())
        self.assertEqual(self.client.get(reverse("payments:result", args=[payment.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("payments:fake_gateway", args=[payment.pk])).status_code, 404)


def _resp(payload):
    r = mock.Mock()
    r.json.return_value = payload
    return r


@media_settings
class ProviderGatewayTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.plan = Plan.objects.create(name="نردبان", kind=Plan.Kind.PROMOTE, price=49000, is_active=True)
        self.payment = Payment.objects.create(user=self.user, plan=self.plan, amount=49000, gateway="x")
        self.rf = RequestFactory()

    @override_settings(PAYMENT_GATEWAY="zarinpal", ZARINPAL_MERCHANT_ID="m", ZARINPAL_SANDBOX=True)
    def test_zarinpal(self):
        gw = gateways.get_gateway()
        self.assertIsInstance(gw, gateways.ZarinpalGateway)
        with mock.patch("apps.payments.gateways.requests.post", return_value=_resp({"data": {"code": 100, "authority": "A000"}})) as post:
            url = gw.start(self.payment, "https://x/cb")
        self.assertEqual(url, "https://sandbox.zarinpal.com/pg/StartPay/A000")
        self.assertEqual(post.call_args[1]["json"]["amount"], 490000)  # rial
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.authority, "A000")

        with mock.patch("apps.payments.gateways.requests.post", return_value=_resp({"data": {"code": -9}})):
            self.assertIsNone(gw.start(self.payment, "https://x/cb"))
        with mock.patch("apps.payments.gateways.requests.post", side_effect=gateways.requests.ConnectionError()):
            self.assertIsNone(gw.start(self.payment, "https://x/cb"))

        req_ok = self.rf.get("/pay/callback/?Authority=A000&Status=OK")
        with mock.patch("apps.payments.gateways.requests.post", return_value=_resp({"data": {"code": 100, "ref_id": 777}})):
            self.assertEqual(gw.verify(self.payment, req_ok), (True, "777"))
        with mock.patch("apps.payments.gateways.requests.post", return_value=_resp({"data": {"code": -51}})):
            self.assertEqual(gw.verify(self.payment, req_ok), (False, ""))
        req_nok = self.rf.get("/pay/callback/?Authority=A000&Status=NOK")
        with mock.patch("apps.payments.gateways.requests.post") as post:
            self.assertEqual(gw.verify(self.payment, req_nok), (False, ""))
            post.assert_not_called()

    @override_settings(PAYMENT_GATEWAY="zarinpal", ZARINPAL_MERCHANT_ID="m")
    def test_zarinpal_callback_view_finds_payment_by_authority(self):
        self.payment.authority = "A123"
        self.payment.gateway = "zarinpal"
        self.payment.save()
        with mock.patch("apps.payments.gateways.requests.post", return_value=_resp({"data": {"code": 100, "ref_id": 5}})):
            r = self.client.get(reverse("payments:callback") + "?Authority=A123&Status=OK")
        self.assertRedirects(r, reverse("payments:result", args=[self.payment.pk]), fetch_redirect_response=False)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PAID)
        self.assertEqual(self.payment.ref_id, "5")

    @override_settings(PAYMENT_GATEWAY="idpay", IDPAY_API_KEY="k", IDPAY_SANDBOX=True)
    def test_idpay(self):
        gw = gateways.get_gateway()
        self.assertIsInstance(gw, gateways.IdpayGateway)
        with mock.patch("apps.payments.gateways.requests.post", return_value=_resp({"id": "ID1", "link": "https://idpay.ir/p/ws/ID1"})) as post:
            self.assertEqual(gw.start(self.payment, "https://x/cb"), "https://idpay.ir/p/ws/ID1")
        self.assertEqual(post.call_args[1]["headers"]["X-SANDBOX"], "1")
        self.assertEqual(post.call_args[1]["headers"]["X-API-KEY"], "k")
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.authority, "ID1")
        with mock.patch("apps.payments.gateways.requests.post", return_value=_resp({"error_code": 11})):
            self.assertIsNone(gw.start(self.payment, "https://x/cb"))

        req = self.rf.post("/pay/callback/", {"id": "ID1", "order_id": str(self.payment.pk), "status": "10"})
        with mock.patch("apps.payments.gateways.requests.post", return_value=_resp({"status": 100, "track_id": 42})):
            self.assertEqual(gw.verify(self.payment, req), (True, "42"))
        with mock.patch("apps.payments.gateways.requests.post", return_value=_resp({"status": 4})):
            self.assertEqual(gw.verify(self.payment, req), (False, ""))
        with mock.patch("apps.payments.gateways.requests.post", side_effect=ValueError("bad json")):
            self.assertEqual(gw.verify(self.payment, req), (False, ""))

    @override_settings(PAYMENT_GATEWAY="idpay", IDPAY_API_KEY="k")
    def test_idpay_callback_view_posts_without_csrf(self):
        self.payment.authority = "ID9"
        self.payment.gateway = "idpay"
        self.payment.save()
        with mock.patch("apps.payments.gateways.requests.post", return_value=_resp({"status": 100, "track_id": 1})):
            r = self.client.post(reverse("payments:callback"), {"id": "ID9", "order_id": str(self.payment.pk), "status": "10"})
        self.assertEqual(r.status_code, 302)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PAID)

    @override_settings(PAYMENT_GATEWAY="nonsense")
    def test_unknown_gateway_falls_back_to_fake(self):
        self.assertIsInstance(gateways.get_gateway(), gateways.FakeGateway)
