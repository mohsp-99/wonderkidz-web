# WonderKidz Web

The WonderKidz classifieds platform — a buy/sell board for kids' toys, on the Divar model, scoped to one vertical. Parents post structured listings (age range, condition, completeness, brand, original price); buyers search, filter, and contact the seller by phone reveal or in-app chat. The platform does not handle delivery or payment between users. Persian, RTL, mobile-first, server-rendered.

Planning, research, and the UI mockups this build follows live in the separate [wonderkidz-planning](https://github.com/mohsp-99/wonderkidz-planning) repo (pivot brief, build proposal, tech-stack doc, stakeholder questions with defaults). Where an answer was missing, the documented default applies.

## Stack

Django 5 · Django templates + HTMX + Alpine.js · the mockup design system as plain CSS · PostgreSQL (SQLite for local dev) · Redis (optional) · Pillow image pipeline (WebP variants) · WhiteNoise · Docker.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # defaults: SQLite, console OTP, fake payment gateway
python manage.py migrate
python manage.py seed_demo      # demo content mirroring the mockups (~10 s, generates images)
python manage.py runserver
```

Open http://localhost:8000. Log in with **any phone number** and OTP **12345** (`OTP_DEV_CODE` in `.env`; with it unset the code is printed to the console by the `console` SMS backend).

Seeded accounts:

| Role | Phone | Notes |
|---|---|---|
| Operator / superuser | `09120000000` | Django admin password `admin`; moderation panel at `/panel/` |
| Parent (مریم ر.) | `09123456789` | has live, pending, rejected and sold listings, chats, saved search |
| Official store | `09128890878` | first-party inventory, labelled "فروشگاه وندرکیدز" |

## Plug-and-play integrations

Everything external is behind an interface and selected by an env var. Nothing in the critical path depends on a service that blocks Iran.

| Concern | Setting | Options | Extra env vars |
|---|---|---|---|
| SMS / OTP | `SMS_BACKEND` | `console` (default), `kavenegar`, `smsir` | `KAVENEGAR_API_KEY`, `KAVENEGAR_OTP_TEMPLATE`, `SMSIR_API_KEY`, `SMSIR_OTP_TEMPLATE_ID` |
| Payment gateway | `PAYMENT_GATEWAY` | `fake` (default), `zarinpal`, `idpay` | `ZARINPAL_MERCHANT_ID`, `ZARINPAL_SANDBOX`, `IDPAY_API_KEY`, `IDPAY_SANDBOX` |
| Media storage | `S3_BUCKET` | local disk when empty; any S3-compatible bucket (Arvan) when set | `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION`, `S3_PUBLIC_URL` |
| Database | `DATABASE_URL` | SQLite when empty; `postgres://…` | — |
| Cache / rate limits | `REDIS_URL` | in-memory when empty | — |

Payments are wired but dormant: `Plan` rows exist (promoted listing, seller subscription) with `is_active=False`, so a fee can be switched on from the admin without a migration. The `fake` gateway renders an in-app page with "پرداخت موفق / انصراف" buttons so the whole flow is testable locally.

Other product switches: `MODERATION_MODEL` (`ai_first` default, `pre_approval`, `post_review`), `LISTING_TTL_DAYS` (30), `NEW_ACCOUNT_LISTING_CAP` (5), `OTP_DEV_CODE` (dev only — leave empty in production).

## Management commands

| Command | What it does |
|---|---|
| `seed_demo [--flush]` | Idempotent demo data: cities/districts, category tree with safety tips, brands, users, ~40 listings with generated images, chats, reports, plans. `--flush` wipes listings/chat/reports/non-superuser users first. |
| `expire_listings` | Nightly sweep: live listings past `expires_at` become expired; lapsed promotions are cleared. Run from cron / a scheduled job. |

## Project layout

```
config/            settings, urls, wsgi/asgi
apps/core/         Persian text + Jalali date helpers, template filters, image pipeline, seed command
apps/catalog/      City, District, Category (tree + safety tips), Brand
apps/accounts/     phone-OTP User model, SMS backends, login/profile
apps/listings/     Listing (all types on one schema), images, saved, phone reveals, reports, search, post flow
apps/chat/         polling-based buyer–seller chat
apps/moderation/   operator panel: review queue, reports, users, decisions, stats
apps/payments/     Plan / Payment + gateway abstraction (fake, Zarinpal, IDPay)
templates/         server-rendered Persian RTL templates (extend base.html)
static/            design system CSS from the mockups, self-hosted Vazirmatn, htmx, Alpine
```

## Tests

```bash
python manage.py test
```

CI (`.github/workflows/ci.yml`) runs ruff, `manage.py check`, a migrations-in-sync check, and the test suite on every push; the Docker image is built on `main`.

## Deployment

**Docker Compose** (app + PostgreSQL 16 + Redis 7):

```bash
cp .env.example .env    # set SECRET_KEY, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, SITE_URL, real SMS/payment keys
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```

The image runs `collectstatic` at build time (WhiteNoise serves static files) and `migrate` on start. Put a TLS-terminating proxy (Caddy / ArvanCloud CDN) in front; `SECURE_PROXY_SSL_HEADER` is honoured when `DEBUG=false`.

**Hamravesh / Arvan Cloud**: the same image works on a managed container platform — attach managed Postgres and Redis, set `DATABASE_URL` / `REDIS_URL`, point `S3_*` at an Arvan object-storage bucket so uploads survive redeploys, and schedule `python manage.py expire_listings` nightly. Nightly `pg_dump` to a second region is the documented backup plan (see the tech-stack doc).

## Configuration reference

See `.env.example` for every variable with a comment.
