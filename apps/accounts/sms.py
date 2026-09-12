"""Plug-and-play SMS / OTP backends.

Selected by settings.SMS_BACKEND: console | kavenegar | smsir.
`send_otp(phone, code)` and `send_sms(phone, text)` never raise — delivery
failures are logged so a provider outage can't break login or notifications.
"""
import logging

import requests
from django.conf import settings
from django.core.cache import cache

log = logging.getLogger("wonderkidz.sms")


class BaseBackend:
    name = "base"

    def send_otp(self, phone: str, code: str) -> bool:
        raise NotImplementedError

    def send_sms(self, phone: str, text: str) -> bool:
        raise NotImplementedError


class ConsoleBackend(BaseBackend):
    """Development backend: prints codes to stdout/log and remembers the last one in cache."""

    name = "console"

    def send_otp(self, phone, code):
        cache.set(f"otp-last:{phone}", code, settings.OTP_TTL_SECONDS)
        msg = f"[SMS/OTP] {phone} -> کد تأیید وندرکیدز: {code}"
        print(msg)
        log.info(msg)
        return True

    def send_sms(self, phone, text):
        msg = f"[SMS] {phone} -> {text}"
        print(msg)
        log.info(msg)
        return True


class KavenegarBackend(BaseBackend):
    name = "kavenegar"
    base = "https://api.kavenegar.com/v1/{key}/"

    def _url(self, path):
        return self.base.format(key=settings.KAVENEGAR_API_KEY) + path

    def send_otp(self, phone, code):
        r = requests.post(
            self._url("verify/lookup.json"),
            data={"receptor": phone, "token": code, "template": settings.KAVENEGAR_OTP_TEMPLATE},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("return", {}).get("status") == 200

    def send_sms(self, phone, text):
        r = requests.post(self._url("sms/send.json"), data={"receptor": phone, "message": text}, timeout=10)
        r.raise_for_status()
        return r.json().get("return", {}).get("status") == 200


class SmsIrBackend(BaseBackend):
    name = "smsir"
    base = "https://api.sms.ir/v1/"

    def _headers(self):
        return {"x-api-key": settings.SMSIR_API_KEY, "Content-Type": "application/json", "Accept": "application/json"}

    def send_otp(self, phone, code):
        r = requests.post(
            self.base + "send/verify",
            json={
                "mobile": phone,
                "templateId": settings.SMSIR_OTP_TEMPLATE_ID,
                "parameters": [{"name": "CODE", "value": code}],
            },
            headers=self._headers(),
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("status") == 1

    def send_sms(self, phone, text):
        r = requests.post(
            self.base + "send/bulk",
            json={"lineNumber": None, "messageText": text, "mobiles": [phone]},
            headers=self._headers(),
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("status") == 1


BACKENDS = {"console": ConsoleBackend, "kavenegar": KavenegarBackend, "smsir": SmsIrBackend}


def get_backend() -> BaseBackend:
    cls = BACKENDS.get(getattr(settings, "SMS_BACKEND", "console"), ConsoleBackend)
    return cls()


def send_otp(phone: str, code: str) -> bool:
    try:
        return bool(get_backend().send_otp(phone, code))
    except Exception:  # noqa: BLE001 — never let a provider outage raise into the login flow
        log.exception("OTP send failed for %s", phone)
        return False


def send_sms(phone: str, text: str) -> bool:
    try:
        return bool(get_backend().send_sms(phone, text))
    except Exception:  # noqa: BLE001
        log.exception("SMS send failed for %s", phone)
        return False
