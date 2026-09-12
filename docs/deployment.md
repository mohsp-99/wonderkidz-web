# Deployment

How WonderKidz runs outside a developer laptop: the Docker image, the compose stack, the environment variables production needs, the CI pipeline, and the cut-over notes for the old wonderkidz.net URLs. Everything here describes files that exist in the repo (`Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`, `config/settings.py`); hosting-provider steps are marked as recommendations.

Related: [operations.md](operations.md) · [integrations.md](integrations.md) · [architecture.md](architecture.md) · [getting-started.md](getting-started.md) · [decisions/0003](decisions/0003-sqlite-and-local-disk-defaults.md)

## Environments

| Environment | Database | Cache | Media | Static | Process | How |
|---|---|---|---|---|---|---|
| Local dev | SQLite (`db.sqlite3`) | LocMem | `media/` on disk | Django dev server | `runserver` | `scripts/wk start` (see [operations.md](operations.md)) |
| Docker compose | Postgres 16 (`db` service) | Redis 7 (`redis` service) | `media` named volume | WhiteNoise from the image | gunicorn, 3 workers | `docker compose up --build` |
| Production (recommended) | Managed Postgres (Hamravesh add-on or Arvan DBaaS) | Managed Redis | Arvan object storage via `S3_*` | WhiteNoise, cached by ArvanCloud CDN | gunicorn behind the platform's TLS proxy or Caddy on a VM | same image as compose |

The application is one deployable unit: one image, one database, no separate API or frontend. Selecting Postgres, Redis and object storage is purely a matter of environment variables (`DATABASE_URL`, `REDIS_URL`, `S3_BUCKET`); the code path does not change.

## The Docker image

`Dockerfile` builds on `python:3.12-slim`:

1. Installs `libpq5` (runtime for psycopg) and `curl` (used by the healthcheck).
2. Installs `requirements.txt`.
3. Copies the source, then runs `collectstatic` at **build time** with a throwaway `SECRET_KEY=build DEBUG=false`. Static files (the mockup CSS, the vendored htmx/Alpine, the Vazirmatn font) are baked into the image under `staticfiles/` and served by WhiteNoise with compressed, hashed filenames.
4. Switches to an unprivileged `app` user.
5. Declares a healthcheck on `/robots.txt` every 30 s.
6. Default command: `gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60`.

`.dockerignore` keeps `.venv`, `.git`, `.env`, `db.sqlite3`, `media/`, `staticfiles/` and caches out of the build context. The image therefore contains no secrets and no user uploads.

Note the Python version skew: the image uses 3.12, the local venv on the original dev machine is 3.10, and `pyproject.toml` targets py310. Keep code 3.10-compatible.

## docker-compose

`docker-compose.yml` defines three services:

| Service | Image | Purpose | Persistent volume |
|---|---|---|---|
| `web` | built from `Dockerfile` | migrates on start (`python manage.py migrate --noinput && gunicorn …`), listens on `8000:8000` | `media:/app/media` |
| `db` | `postgres:16-alpine` | database `wonderkidz` / user `wonderkidz` / password `wonderkidz`, healthchecked with `pg_isready` | `pgdata` |
| `redis` | `redis:7-alpine` | cache + rate-limit counters | `redisdata` |

`web` reads `.env` via `env_file` and then overrides `DATABASE_URL`, `REDIS_URL` and `DEBUG=false` in `environment`, so a local `.env` copied from `.env.example` works unchanged. All three services restart `unless-stopped`; `web` waits for the database healthcheck.

```bash
cp .env.example .env            # then set SECRET_KEY, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS
docker compose up --build -d
docker compose exec web python manage.py seed_demo      # optional demo content
docker compose exec web python manage.py createsuperuser
docker compose logs -f web
```

The compose database password is a development default. For anything internet-facing, either change it in `docker-compose.yml` or point `DATABASE_URL` at a managed database instead.

## Production environment variables

All settings are read from the environment (or `.env`) in `config/settings.py`. Required or strongly recommended in production:

| Variable | Required | Notes |
|---|---|---|
| `SECRET_KEY` | yes | long random string; the default `dev-insecure-change-me` must never reach production |
| `DEBUG` | yes, `false` | turns on manifest static storage, secure cookies, HSTS (30 days), `SECURE_PROXY_SSL_HEADER` |
| `ALLOWED_HOSTS` | yes | comma-separated, e.g. `wonderkidz.net,www.wonderkidz.net`; with `DEBUG=false` the default is empty and every request is refused |
| `CSRF_TRUSTED_ORIGINS` | yes | comma-separated with scheme, e.g. `https://wonderkidz.net` |
| `SITE_URL` | yes | used for canonical links, JSON-LD and the sitemap |
| `DATABASE_URL` | yes | `postgres://user:pass@host:5432/dbname` (parsed by `dj-database-url`, `conn_max_age=60`) |
| `REDIS_URL` | recommended | enables the Redis cache; without it rate limits live in per-process memory and reset on restart |
| `S3_BUCKET`, `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION`, `S3_PUBLIC_URL` | recommended | switches media to object storage (`storages.backends.s3.S3Storage`, public-read, no querystring auth); `S3_PUBLIC_URL` becomes `MEDIA_URL` so the CDN serves image bytes |
| `SMS_BACKEND` + provider keys | yes | `kavenegar` or `smsir`; see [integrations.md](integrations.md). With `console` nobody can log in. |
| `OTP_DEV_CODE` | must be **empty** | any non-empty value is a universal login code |
| `PAYMENT_GATEWAY` + keys | when charging | `zarinpal` or `idpay`; `fake` auto-approves payments |
| `MODERATION_MODEL` | optional | `ai_first` (default), `pre_approval`, `post_review` — see [moderation.md](moderation.md) |
| `LISTING_TTL_DAYS`, `NEW_ACCOUNT_LISTING_CAP` | optional | defaults 30 and 5 |
| `LOG_LEVEL` | optional | default `INFO`, plain-text to stdout |

`.env.example` lists every variable with a comment.

## HTTPS and proxies

With `DEBUG=false` the settings enable `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`, secure session and CSRF cookies, and HSTS. The app itself speaks plain HTTP on port 8000 and expects a TLS-terminating proxy in front:

- **Hamravesh** (managed containers): the platform terminates TLS and sets `X-Forwarded-Proto`; deploy the image, attach the Postgres/Redis add-ons, set the variables above.
- **Arvan VM**: run the compose stack and put Caddy in front (`reverse_proxy localhost:8000`); Caddy obtains certificates and forwards the proto header automatically.
- **ArvanCloud CDN/DNS** in front of either, caching anonymous category/listing pages and the object-storage bucket. The current wonderkidz.net certificate chain is broken (untrusted CA, per the planning crawl); cutting over to CDN-issued TLS fixes that on day one.

The service worker (`/sw.js`) only registers on `https:`; installability and the PWA manifest therefore need real TLS.

## Static files and migrations on deploy

- Static files are collected at image build; no runtime step. WhiteNoise serves them with far-future cache headers when `DEBUG=false` (`CompressedManifestStaticFilesStorage`).
- Migrations run on container start in the compose command. On a platform that runs several replicas, run `python manage.py migrate --noinput` once as a release step instead, then start the web processes.
- `python manage.py check --deploy` is a useful pre-flight; CI already runs `check` and `makemigrations --check`.

## CI pipeline

`.github/workflows/ci.yml`, on every push to `main` and every pull request:

| Job | Steps |
|---|---|
| `test` (Python 3.12, `SECRET_KEY=ci`, `DEBUG=true`, `OTP_DEV_CODE=12345`) | `pip install -r requirements.txt ruff` → `ruff check .` → `manage.py check` → `manage.py makemigrations --check --dry-run` → `manage.py test --noinput` |
| `docker` (only on push to `main`, after `test`) | builds the image with Buildx and GitHub Actions cache, tagged `wonderkidz-web:<sha>`, **not pushed** |

Pushing to a registry and deploying is intentionally left out until a hosting account exists; add a `docker/login-action` + `push: true` step and the provider's deploy hook when it does. Because `ruff` runs in CI with `E,F,W,I` (E501 ignored), unformatted imports fail the build.

## First-deploy checklist

1. Accounts under the company name (planning phase 0): SMS line + OTP template approved (Kavenegar, SMS.ir fallback), payment gateway (Zarinpal, IDPay backup), enamad, hosting, object storage, domain/DNS/Search Console access.
2. Provision Postgres and Redis; create the bucket with public-read objects and a CDN in front.
3. Set every variable in the table above; double-check `OTP_DEV_CODE` is empty and `PAYMENT_GATEWAY` is not `fake`.
4. Build and push the image; run `migrate`; start gunicorn behind TLS.
5. `python manage.py createsuperuser` (phone + password) for the operator, then mark additional operators `is_staff` in Django admin.
6. Load reference data: categories, districts, brands. `seed_demo` creates them along with demo listings; for production, run it once on an empty database, then `--flush` removes the demo listings/users but keeps categories, districts and brands, or enter them by hand in `/admin/`.
7. Verify: `/robots.txt`, `/sitemap.xml`, a category page, OTP login with a real phone, image upload, phone reveal, a chat message, an approval in `/panel/`.
8. Schedule `expire_listings` nightly and database backups (see [operations.md](operations.md)).
9. Point DNS, submit the sitemap in Search Console, and deploy the redirect map below.

## Cutting over from the old wonderkidz.net

The old site is WordPress + WooCommerce Bookings (see `../wonderkidz-planning/crawl/current-site-ui.md`). Its indexed URLs should 301 to the closest new page so the SEO footprint carries over. The redirects are **not implemented in the app**; put them in the CDN/proxy layer (ArvanCloud page rules or Caddy `redir`). Proposed map, using the category slugs created by `seed_demo`:

| Old URL | New URL | Note |
|---|---|---|
| `/shop/` | `/s/` | full catalogue → search |
| `/category/puzzle/` | `/s/building/` | puzzles live under لگو و ساختنی (`puzzles` child) — use `/s/puzzles/` if you prefer the leaf |
| `/category/construction/` | `/s/building/` | |
| `/category/educational/` | `/s/educational/` | |
| `/category/mental_game/` | `/s/board-games/` | |
| `/category/skills/` | `/s/educational/` | closest match; or `/s/dexterity/` |
| `/category/art/` | `/s/arts-crafts/` | |
| `/category/essentials/` | `/s/baby/` | |
| `/age/0-18-month/` | `/s/?age=0-1` | age is a filter, not a path; the app's age keys are `0-1`, `1-3`, `3-5`, `5-8`, `8+` |
| `/age/18-months-to-3-years/` | `/s/?age=1-3` | |
| `/age/3-5-years/` | `/s/?age=3-5` | |
| `/age/5-7-years/` | `/s/?age=5-8` | |
| `/age/up-to-7-years/` | `/s/?age=8%2B` | |
| `/brand/lego/`, `/brand/janod/`, `/brand/picassotiles/`, `/brand/viga/` | `/s/?brand=lego` etc. | brand slugs match `Brand.slug` from the seed |
| `/brand/cobi/`, `/brand/md/`, `/brand/playgo/`, `/brand/zuru/` | `/s/` | brands not seeded; add them in admin first if you want exact redirects |
| `/product/<slug>/` | `/s/` (or `/u/<official-account-id>/`) | rental products become first-party listings with new codes; no 1:1 mapping |
| `/about-us/`, `/contact-us/`, `/faqs/`, `/terms-conditions/`, `/privacy-policies/` | `/p/about/`, `/p/about/`, `/p/faq/`, `/p/terms/`, `/p/privacy/` | static pages exist under `/p/<slug>/` |
| `/my-account/`, `/cart/`, `/wishlist/`, `/blog/` | `/login/`, `/`, `/me/#t-saved`, `/` | no cart, no blog in v1 |

Also add `noindex` for `/panel/`, `/chat/`, `/me/` (already `Disallow`ed in `templates/robots.txt`) and keep `/sitemap.xml` reachable for crawlers.
