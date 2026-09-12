"""
Plug-and-play payment gateways.

Every gateway implements:
    start(payment, callback_url) -> redirect_url | None
    verify(payment, request)     -> (ok: bool, ref_id: str)

Nothing here raises into views: network / provider failures return None / (False, "").
Select with settings.PAYMENT_GATEWAY = fake | zarinpal | idpay.
"""
import logging
import uuid

import requests
from django.conf import settings
from django.urls import reverse

log = logging.getLogger(__name__)
TIMEOUT = 15


class Gateway:
    name = "base"

    def start(self, payment, callback_url):  # pragma: no cover - interface
        raise NotImplementedError

    def verify(self, payment, request):  # pragma: no cover - interface
        raise NotImplementedError


class FakeGateway(Gateway):
    """Local stand-in: redirects to an in-app page with 'pay' / 'cancel' buttons."""

    name = "fake"

    def start(self, payment, callback_url):
        payment.authority = f"FAKE-{uuid.uuid4().hex[:12]}"
        payment.save(update_fields=["authority"])
        return reverse("payments:fake_gateway", args=[payment.pk])

    def verify(self, payment, request):
        if request.GET.get("status") == "ok":
            return True, f"FAKE{payment.pk:08d}"
        return False, ""


class ZarinpalGateway(Gateway):
    name = "zarinpal"

    @property
    def api_base(self):
        host = "https://sandbox.zarinpal.com" if settings.ZARINPAL_SANDBOX else "https://api.zarinpal.com"
        return f"{host}/pg/v4/payment"

    @property
    def start_pay_base(self):
        host = "https://sandbox.zarinpal.com" if settings.ZARINPAL_SANDBOX else "https://www.zarinpal.com"
        return f"{host}/pg/StartPay"

    def start(self, payment, callback_url):
        payload = {
            "merchant_id": settings.ZARINPAL_MERCHANT_ID,
            "amount": int(payment.amount) * 10,  # rial
            "callback_url": callback_url,
            "description": f"وندرکیدز — {payment.plan.name}",
            "metadata": {"mobile": payment.user.phone, "order_id": str(payment.pk)},
        }
        try:
            r = requests.post(f"{self.api_base}/request.json", json=payload, timeout=TIMEOUT)
            data = r.json().get("data") or {}
        except (requests.RequestException, ValueError) as e:
            log.warning("zarinpal start failed: %s", e)
            return None
        if data.get("code") not in (100, 101) or not data.get("authority"):
            log.warning("zarinpal start rejected: %s", data)
            return None
        payment.authority = data["authority"]
        payment.save(update_fields=["authority"])
        return f"{self.start_pay_base}/{payment.authority}"

    def verify(self, payment, request):
        if request.GET.get("Status") != "OK":
            return False, ""
        payload = {
            "merchant_id": settings.ZARINPAL_MERCHANT_ID,
            "amount": int(payment.amount) * 10,
            "authority": payment.authority,
        }
        try:
            r = requests.post(f"{self.api_base}/verify.json", json=payload, timeout=TIMEOUT)
            data = r.json().get("data") or {}
        except (requests.RequestException, ValueError) as e:
            log.warning("zarinpal verify failed: %s", e)
            return False, ""
        if data.get("code") in (100, 101):
            return True, str(data.get("ref_id", ""))
        return False, ""


class IdpayGateway(Gateway):
    name = "idpay"
    api_base = "https://api.idpay.ir/v1.1/payment"

    @property
    def headers(self):
        return {
            "Content-Type": "application/json",
            "X-API-KEY": settings.IDPAY_API_KEY,
            "X-SANDBOX": "1" if settings.IDPAY_SANDBOX else "0",
        }

    def start(self, payment, callback_url):
        payload = {
            "order_id": str(payment.pk),
            "amount": int(payment.amount) * 10,  # rial
            "phone": payment.user.phone,
            "desc": f"وندرکیدز — {payment.plan.name}",
            "callback": callback_url,
        }
        try:
            r = requests.post(self.api_base, json=payload, headers=self.headers, timeout=TIMEOUT)
            data = r.json()
        except (requests.RequestException, ValueError) as e:
            log.warning("idpay start failed: %s", e)
            return None
        if not data.get("id") or not data.get("link"):
            log.warning("idpay start rejected: %s", data)
            return None
        payment.authority = data["id"]
        payment.save(update_fields=["authority"])
        return data["link"]

    def verify(self, payment, request):
        # IDPay posts back id/order_id/status; GET fallback supported for sandbox testing.
        src = request.POST if request.method == "POST" else request.GET
        pid = src.get("id") or payment.authority
        payload = {"id": pid, "order_id": str(payment.pk)}
        try:
            r = requests.post(f"{self.api_base}/verify", json=payload, headers=self.headers, timeout=TIMEOUT)
            data = r.json()
        except (requests.RequestException, ValueError) as e:
            log.warning("idpay verify failed: %s", e)
            return False, ""
        if int(data.get("status", 0)) == 100:
            return True, str(data.get("track_id", ""))
        return False, ""


GATEWAYS = {g.name: g for g in (FakeGateway, ZarinpalGateway, IdpayGateway)}


def get_gateway():
    cls = GATEWAYS.get(settings.PAYMENT_GATEWAY, FakeGateway)
    return cls()
