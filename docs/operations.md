# Operations runbook

Day-2 reference for whoever runs WonderKidz: the dev runner, management commands, operator accounts, backups, monitoring, the abuse levers and their settings, and the fixes for the problems that have actually come up. Commands are shown for the local runner; in Docker prefix them with `docker compose exec web`.

Related: [deployment.md](deployment.md) · [moderation.md](moderation.md) · [integrations.md](integrations.md) · [testing.md](testing.md)

## The dev runner: `scripts/wk`

`scripts/wk` is a bash wrapper around the virtualenv and `manage.py`. It is idempotent and safe to re-run.

| Command | What it does |
|---|---|
| `scripts/wk setup` | creates `.venv` if missing, installs `requirements.txt` (falls back to pypi.org if the local pip mirror 404s), installs `ruff`, copies `.env.example` → `.env` if absent, migrates, and seeds demo data when the `Listing` table is empty |
| `scripts/wk start` | refuses if the port is busy, runs `check`, applies pending migrations, starts `runserver --noreload` detached with `setsid`, writes `.run/server.pid`, logs to `.run/server.log`, waits up to 20 s for `/` to answer, prints the OTP dev code |
| `scripts/wk stop` | kills the PID from the pid file plus any `manage.py runserver` on the same port found via `/proc`, waits, then `kill -9` |
| `scripts/wk restart`, `status`, `logs [n]` | as named; `logs` tails `.run/server.log` |
| `scripts/wk fg` | foreground server with autoreload (Ctrl+C to stop) |
| `scripts/wk test [args]` | `ruff check .` → `makemigrations --check` → `manage.py test --noinput args` |
| `scripts/wk seed [--flush]` | `seed_demo` |
| `scripts/wk shell`, `scripts/wk manage <cmd>` | Django shell / any management command |

Environment overrides: `WK_PORT` (default 8000), `WK_HOST` (default 0.0.0.0), `WK_PIP_INDEX` (default `https://pypi.org/simple`). `.run/` is git-ignored.

## Management commands

| Command | Purpose |
|---|---|
| `manage.py seed_demo` | idempotent reference + demo data: cities/districts, 10 root categories with children and safety tips, 8 brands, 7 users (operator `09120000000` with admin password `admin`, official store `09128890878`, five parents), ~40 listings across every status with generated images, 4 chats, 4 reports, 2 inactive plans. Re-running creates only what is missing. |
| `manage.py seed_demo --flush` | deletes listings (and their image files), chats, reports and **all non-superuser users** first, then reseeds. Categories, districts, brands and superusers survive. Never run this against production data. |
| `manage.py expire_listings` | moves `LIVE` listings whose `expires_at` has passed to `EXPIRED`. Uses `apps.listings.services.expire_listings`. Run nightly. |
| `manage.py createsuperuser` | prompts for phone and password (the custom `User` model has no username/email) |
| `manage.py collectstatic` | only needed outside Docker with `DEBUG=false` |

### Scheduling the nightly sweep

There is no in-process scheduler and no django-rq worker yet (Redis is used only as a cache). Use the host's cron or a compose sidecar:

```cron
# crontab on the host, 03:30 Tehran time
30 3 * * * cd /srv/wonderkidz-web && docker compose exec -T web python manage.py expire_listings >> /var/log/wonderkidz-expire.log 2>&1
```

Or add a service to `docker-compose.yml` that loops `sleep 86400; python manage.py expire_listings`. Renewing an expired listing (`listings:renew`) sets it back to `LIVE` with a fresh 30-day window.

Note: the `expire_listings` command falls back to inline logic that also clears lapsed `is_promoted` flags, but the service function it prefers (`apps/listings/services.py`) does **not** clear `is_promoted`/`promoted_until`. Until that is unified, a promoted listing keeps sorting first (`is_promoted` drives ordering on home and search) after `promoted_until` has passed.

## Operator accounts

- **Django admin** (`/admin/`) needs `is_staff` and the relevant permissions; superusers have everything. Login is phone + password (set via `createsuperuser` or the admin's user form).
- **Operator panel** (`/panel/`) needs only `is_staff`; it is gated by `operator_required` in `apps/moderation/views.py`, which redirects anonymous users to `/login/?next=` and non-staff to the home page. Operators log in like everyone else, with phone OTP.
- Use `/panel/` for daily moderation (queue, reports, users, listings, stats, decisions). Use `/admin/` for reference data (categories, districts, brands, plans), bulk edits and anything the panel does not expose.
- To promote a parent to operator: `/admin/accounts/user/`, tick `is_staff`. To demote, untick. Banning is a separate flag (`is_banned` + `ban_reason`) and is done from the panel's user page.

## Backups

Not automated in the repo. Recommended (from the tech-stack doc):

- Nightly `pg_dump -Fc` of the Postgres database, uploaded to an object-storage bucket in a **second** Arvan region, 30-day retention. With compose: `docker compose exec -T db pg_dump -U wonderkidz -Fc wonderkidz > backup-$(date +%F).dump`.
- Object storage holds the images; enable bucket versioning so an accidental delete is recoverable.
- SQLite in development: the whole state is `db.sqlite3` + `media/`; copy both.
- **Restore drill before launch**: restore the dump into a fresh database (`pg_restore -d wonderkidz backup.dump`), point a staging container at it, log in, open a listing, confirm images resolve. Document the time it took.

## Logs

- Local runner: `.run/server.log` (`scripts/wk logs`).
- Docker: stdout/stderr, `docker compose logs -f web`. Application logging is configured in `config/settings.py` (`LOGGING`): plain-text `asctime level logger: message` to the console, level from `LOG_LEVEL`.
- The console SMS backend logs every OTP and notification as `wonderkidz.sms: [SMS/OTP] <phone> -> <text>`; useful to read codes in development.
- Retention: keep 30 days on host (tech-stack doc). Nothing ships logs off-box.

## Monitoring

**Not wired yet.** The planning stack calls for three self-hosted tools; none has configuration in this repo:

| Tool | Role | What to do |
|---|---|---|
| GlitchTip (Sentry-compatible) | error tracking with Telegram alerts | add `sentry-sdk`, set a DSN from env in `settings.py` |
| Uptime Kuma | probes `/`, `/s/`, and an OTP health endpoint | probe `/robots.txt` (the Docker healthcheck URL) until a dedicated health view exists |
| Umami or Plausible | privacy-friendly analytics: page views, search terms, contact reveals, chat starts | add the script tag to `templates/base.html` behind an env flag |

The operator panel's stats page (`/panel/stats/`) already computes the launch KPIs (listings per status, weekly signups, weekly contacts = conversations + phone reveals, top categories/districts) directly from the database.

## Abuse levers and their settings

| Lever | Where | Setting / value |
|---|---|---|
| OTP requests per phone | `apps/accounts/views.py`, cache key per phone | `OTP_RATE_LIMIT_PER_HOUR` (default 5), `OTP_TTL_SECONDS` 120, `OTP_LENGTH` 5, 5 wrong attempts per code |
| Phone reveals per user | `apps/listings/views.py::reveal_phone`, cache counter | 30 per hour (hard-coded) |
| Active listings per account | `User.listing_cap`, checked in the post view | `NEW_ACCOUNT_LISTING_CAP` (default 5) for new accounts; raise per user in admin; the official account is seeded with 500 |
| Listing lifetime | `Listing.expires_at` | `LISTING_TTL_DAYS` (default 30) |
| Images per listing | form validation | `LISTING_MIN_IMAGES` 1, `LISTING_MAX_IMAGES` 8, 12 MB per file (`apps/core/images.py`) |
| Contact info in listing text | `apps/core/text.py::has_contact_info` | phone numbers, URLs, `@handles`, Telegram/Instagram mentions are rejected by the form |
| Automatic review flags | `apps/listings/services.py::run_auto_checks` | banned keywords (car seats, clothes, formula, nappies) block; price < 25 % of category median, weak hygiene note, single photo, brand-new account warn |
| Review model | `MODERATION_MODEL` | `ai_first` publishes unflagged listings immediately; `pre_approval` queues everything; `post_review` publishes everything and keeps flags for the panel |
| Ban | panel user page | `is_banned` also removes the user's live and pending listings; banned users cannot log in, post or chat |

Rate limits live in the Django cache. Without `REDIS_URL` they are per-process and reset on restart; set `REDIS_URL` in any multi-worker deployment.

## SMS: cost and failure

- Every OTP is a paid message. The rate limit above is a cost control as much as an abuse control; watch the provider dashboard for spikes.
- Notifications (moderation result, first chat message, warnings) go through `apps/accounts/sms.py::send_sms` and respect the user's `notify_*` flags. Failures are logged and never raise.
- **If OTP delivery fails** (provider outage, template rejected): nobody can log in. Switch `SMS_BACKEND` to the approved fallback (`smsir` ↔ `kavenegar`) and restart the web process. Keep both accounts approved at all times; template approval takes days.
- Do not set `OTP_DEV_CODE` in production to "unblock" logins; it is a universal password.

## Secrets rotation

- `SECRET_KEY`: rotating it invalidates every session (users log in again with OTP) and every signed value. Do it in a maintenance window.
- Provider keys (`KAVENEGAR_API_KEY`, `SMSIR_API_KEY`, `ZARINPAL_MERCHANT_ID`, `IDPAY_API_KEY`, `S3_*`): rotate at the provider, update the environment, restart. No code change.
- Nothing secret is in the repo; `.env` is git-ignored and `.dockerignore`d.

## Data retention

- The UI promises that chat messages are kept "up to 6 months for report handling" (`templates/chat/_list.html`, `templates/listings/pages/privacy.html`). **This is not enforced by code**: there is no purge job for `chat.Message`. Add a management command (delete `Message` rows older than 180 days on conversations without open reports) and schedule it next to `expire_listings` before launch, or soften the copy.
- OTP codes accumulate in `accounts.OTPCode`; they are small, but a periodic delete of rows older than a day is cheap hygiene.
- Listings are never hard-deleted by users: `delete` sets `status=REMOVED`; takedowns do the same. Images stay on disk/bucket until removed manually.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `scripts/wk start` says the port is in use | another server (or a stray `runserver`) on 8000 | `scripts/wk stop` (it also hunts stray processes on the port), or `WK_PORT=8001 scripts/wk start` |
| `pip install` fails with a 404 on `archive.ito.gov.ir` | the machine's `~/.config/pip/pip.conf` points at a domestic mirror missing some wheels | `pip install -i https://pypi.org/simple -r requirements.txt` — `scripts/wk setup` does this fallback automatically |
| Nobody receives OTP codes locally | `SMS_BACKEND=console` | read the code from `.run/server.log` or use `OTP_DEV_CODE` (12345 in `.env.example`) |
| Login works but `/panel/` redirects home | user is not `is_staff` | tick it in `/admin/accounts/user/` |
| Emoji show as boxes in headless-Chrome screenshots on Linux | no colour-emoji font installed | `sudo apt install fonts-noto-color-emoji`; real browsers on Windows/macOS/Android are fine |
| Seed images are letters on pastel gradients | same font gap: `seed_demo` renders the category emoji only when `NotoColorEmoji` is present, otherwise a circle with the title's first letter | install the font and `seed_demo --flush` |
| `DisallowedHost` in production | `ALLOWED_HOSTS` empty when `DEBUG=false` | set it (and `CSRF_TRUSTED_ORIGINS`) |
| A parent cannot post: "سقف آگهی" message | at `listing_cap` (pending + live count) | raise `listing_cap` for that user in admin, or wait for a sale/expiry |
| `makemigrations --check` fails in CI | model changed without a migration | run `manage.py makemigrations`, commit the file |
| Persian listing URL gives 404 | a route uses the `slug` converter | routes use `str` on purpose (see [decisions/0007](decisions/0007-unicode-slugs-and-code-urls.md)); keep it that way |
