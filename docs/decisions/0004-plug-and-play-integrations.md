# 0004 — External services behind env-selected backends (SMS, payments, storage)

**Status:** accepted · **Date:** 2026-09-12

## Context

Phone-OTP SMS, the payment gateway and object storage are on the critical path but their accounts (Kavenegar, SMS.ir, Zarinpal, IDPay, Arvan) take days to weeks to obtain under a company name and none existed at build time. The planning docs also require a fallback SMS provider and a backup payment gateway, because provider approval is the least predictable lead time. The user asked for these to be "plug and play".

## Decision

Each concern has one interface, several implementations, and one env var that selects among them:

| Concern | Setting | Implementations |
|---|---|---|
| SMS / OTP | `SMS_BACKEND` | `ConsoleBackend` (logs; default), `KavenegarBackend`, `SmsIrBackend` in `apps/accounts/sms.py`; callers use `send_otp()` / `send_sms()` only |
| Payments | `PAYMENT_GATEWAY` | `FakeGateway` (local approve/cancel page; default), `ZarinpalGateway`, `IdpayGateway` in `apps/payments/gateways.py`; the views only call `start()` and `verify()` |
| Media | `S3_BUCKET` | local disk or S3-compatible storage via Django's `STORAGES` |

Provider calls use `requests` with timeouts, log failures and never raise into a view. Provider code is exercised in tests with `requests.post` mocked. `OTP_DEV_CODE` provides a universal code for development and CI only.

## Consequences

- The whole app, including login and a paid promotion flow, runs and is testable with zero external accounts.
- Switching or falling back is a config change and a restart; the runbook documents the OTP-outage procedure.
- Adding a provider means one class and one branch in `get_backend()` / `get_gateway()`.
- The `console` and `fake` defaults are dangerous in production; deployment docs list them as must-change, and `OTP_DEV_CODE` must be empty.
- Provider APIs were implemented from their public documentation without live credentials; the first real transaction on each provider needs a manual verification.
