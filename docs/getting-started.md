# Getting started

Run WonderKidz locally with SQLite, console-printed OTP codes, a fake payment gateway, and seeded demo content that mirrors the design mockups. Nothing external is needed. `scripts/wk` wraps every routine command so setup and the dev server behave the same on every machine.

Related: [operations.md](operations.md) · [deployment.md](deployment.md) · [testing.md](testing.md)

## Prerequisites

- Python 3.10 or newer (Docker image uses 3.12).
- `git`, `curl`, and internet access for `pip` on first setup.
- Optional: Docker and Docker Compose for the Postgres + Redis variant.

## First run

```bash
git clone https://github.com/mohsp-99/wonderkidz-web.git
cd wonderkidz-web
scripts/wk setup     # venv, dependencies, .env, migrations, demo seed
scripts/wk start     # background dev server on http://localhost:8000
```

`setup` is safe to re-run: it only creates what is missing and only seeds when the database has no listings. If `pip` fails against a slow or incomplete mirror, the script retries against `https://pypi.org/simple` automatically.

## Logging in

Phone number is the identity; there are no passwords on the public site.

| Who | Phone | Notes |
|---|---|---|
| Any new parent | any 11-digit number starting `09` | Registers on first OTP login |
| Parent with history (مریم ر.) | `09123456789` | Live, pending, rejected and sold listings; chats; a saved search |
| Official store | `09128890878` | First-party inventory labelled «فروشگاه وندرکیدز» |
| Operator | `09120000000` | Moderation panel at `/panel/`; Django admin at `/admin/` with password `admin` |

The OTP is `12345` while `OTP_DEV_CODE=12345` is set in `.env`. Remove it to see real codes printed by the console SMS backend in `scripts/wk logs`.

## Daily commands

```bash
scripts/wk status         # running? which port?
scripts/wk logs           # follow the server log
scripts/wk restart        # after changing settings or requirements
scripts/wk stop
scripts/wk fg             # foreground server with autoreload, Ctrl+C to stop
scripts/wk test           # ruff + migration check + tests
scripts/wk seed --flush   # wipe listings/users and reseed
scripts/wk manage shell   # any manage.py command
```

Use `WK_PORT=8010 scripts/wk start` if port 8000 is taken.

## Where things are

| Path | What |
|---|---|
| `config/` | settings (env-driven), root URLs, WSGI/ASGI |
| `apps/core` | Persian text/date helpers, template tags, image pipeline, seed and maintenance commands |
| `apps/accounts` | phone-OTP auth, profiles, SMS backends |
| `apps/catalog` | cities, districts, categories, brands |
| `apps/listings` | listing CRUD, search, detail, moderation auto-checks |
| `apps/chat` | polling chat |
| `apps/moderation` | operator panel |
| `apps/payments` | plans and payment gateways |
| `templates/`, `static/` | server-rendered templates, the mockup design system, vendored htmx/Alpine, self-hosted Vazirmatn |
| `tests/` | the test suite |
| `docs/` | this documentation |

## Try the main flows

1. Browse `/` and `/s/` anonymously; filters, sorting, and category URLs work without login.
2. Log in with a new phone, post a listing at `/new/` with a couple of photos. Under the default `MODERATION_MODEL=ai_first`, a first listing from a brand-new account is flagged and lands in the review queue.
3. Log in as the operator, open `/panel/`, approve it. The seller would receive an SMS (printed to the log).
4. From a second account, open the listing, reveal the phone, start a chat, send a message; the thread polls every four seconds.
5. Visit `/pay/plans/` to see the dormant plans; the fake gateway completes a payment end to end.

## Docker variant

```bash
cp .env.example .env
docker compose up --build
docker compose exec web python manage.py seed_demo
```

This runs Postgres 16 and Redis 7 alongside the app with Gunicorn on port 8000. See [deployment.md](deployment.md) for production settings.
