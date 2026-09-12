# Architecture

WonderKidz is a single Django 5 application: one deployable unit, one database, server-rendered Persian RTL pages, with HTMX for server-driven partial updates and Alpine.js for purely client-side state. There is no API layer and no JavaScript build step; every listing, category and static page is crawlable HTML. External services (SMS, payments, object storage, cache) sit behind env-selected backends so the app runs out of the box on SQLite with console OTP and a fake payment gateway.

Related: [data-model.md](data-model.md) · [moderation.md](moderation.md) · [integrations.md](integrations.md) · [frontend.md](frontend.md) · [search-and-seo.md](search-and-seo.md) · [deployment.md](deployment.md)

## Request flow

```
browser ──► WhiteNoise (static) ──► Django middleware ──► URLconf ──► view ──► template ──► HTML
                                        │
                                        ├─ SessionMiddleware      session cookie, 90-day age (phone is the identity)
                                        ├─ CsrfViewMiddleware     every POST, incl. htmx (token injected via hx-headers on <body>)
                                        ├─ AuthenticationMiddleware
                                        ├─ MessageMiddleware      flash messages rendered at the top of base.html
                                        └─ HtmxMiddleware         sets request.htmx (apps/core/middleware.py)
```

A view either renders a full page (`render(...)`) or, when `request.htmx` is true, a fragment template (files prefixed with `_`). Fragment views are the only place the two paths diverge; the data access is the same.

## Repository layout

| Path | Role |
|---|---|
| `config/settings.py` | All settings; env-driven via `env()` helper and `.env` (python-dotenv). Product constants live at the bottom (`LISTING_TTL_DAYS`, `MODERATION_MODEL`, `IMAGE_SIZES`, OTP/payment switches). |
| `config/urls.py` | Root URLconf: admin, `panel/`, accounts (root-level `login/`, `me/`…), `chat/`, `pay/`, sitemap, robots, manifest, service worker, then listings at `/`. |
| `apps/core` | Cross-cutting helpers: Persian text (`text.py`), Jalali dates (`dates.py`), template tags (`templatetags/fa.py`), image pipeline (`images.py`), htmx middleware, site context processor, management commands (`seed_demo`, `expire_listings`). |
| `apps/catalog` | Reference data: `City`, `District`, `Category` (two-level tree), `Brand`, `AgeRange` choices. Managed in Django admin. |
| `apps/accounts` | Custom `User` (phone = username), `OTPCode`, `SavedSearch`; OTP login flow; SMS backends (`sms.py`); profile and public seller page. |
| `apps/listings` | `Listing`, `ListingImage`, `SavedListing`, `PhoneReveal`, `Report`; home, search, detail, post/edit wizard, owner actions, static pages, sitemaps; `services.py` holds auto-checks and the moderation-model router. |
| `apps/chat` | `Conversation`, `Message`; inbox, thread, polling fragment, send, feedback. |
| `apps/moderation` | `ModerationDecision`; the operator panel at `/panel/` and its services (approve/reject/takedown/ban/warn, stats). |
| `apps/payments` | `Plan`, `Payment`; gateway abstraction (`gateways.py`), start/callback/result views. Dormant at launch. |
| `templates/` | `base.html` + `partials/` (header, footer, card, pagination) + one folder per app. Panel pages extend `panel/base_panel.html`. |
| `static/` | `css/styles.css` (mockup design system, verbatim), `css/app.css` (app additions), `js/app.js`, vendored `htmx.min.js` and `alpine.min.js`, self-hosted Vazirmatn font. |
| `tests/` | Django `TestCase` suite (see [testing.md](testing.md)). |
| `scripts/wk` | Dev runner (setup / start / stop / test / seed). |

## Rendering approach: server HTML, HTMX, Alpine

The rule of thumb: **if the server has to know, it's HTMX; if only the page has to know, it's Alpine; if it navigates, it's a link or form.**

| Interaction | Mechanism | Endpoint / template |
|---|---|---|
| Search "آگهی‌های بیشتر" (load next page) | htmx `hx-get` with `page=N`, `hx-swap="outerHTML"` on a sentinel button; plain link fallback | `listings:search` → `listings/_results.html` |
| Phone reveal | htmx `hx-post`, swaps `#phonebox`; anonymous users get `HX-Redirect` to login. If the user already revealed, `hx-trigger="load"` re-opens the box on page load | `listings:reveal` → `listings/_phone_reveal.html` |
| Save / unsave listing | htmx `hx-post`, swaps the button | `listings:save` → `listings/_save_button.html` |
| Edit-flow image add / delete | htmx `hx-post` returning upload-slot fragments | `listings:upload_image`, `listings:delete_image` → `listings/_upload_slot.html` |
| Chat thread refresh | htmx `hx-get` with `hx-trigger="every 4s"` into `#ct-msgs`; compose form `hx-post` and resets | `chat:messages`, `chat:send` → `chat/_messages.html` |
| Panel approve / reject / resolve / takedown | htmx `hx-post` replacing the action slot with a badge; non-htmx falls back to redirect + flash | `panel:*` views return `<span class="badge …">` |
| Post-a-listing 6-step wizard | Alpine `x-data="postForm(cats, dists)"`: all six steps are in one server-side `<form>`; Alpine only shows one step at a time, validates required fields client-side before advancing, previews images via `DataTransfer`, renders the step-6 preview | `listings:post` / `listings:edit` → `listings/post.html` |
| Report forms, reject box | Alpine booleans (`{open:false}`, `{rej:false}`, `{report:false}`) toggling inline forms that then POST normally | — |
| Header burger, city picker, tabs, filter drawer, gallery thumbs, OTP boxes, digit masks, copy-to-clipboard | Vanilla JS in `static/js/app.js` (ported from the mockup `shared.js`) | — |
| Everything else (filters, sort, owner actions, login) | Plain GET forms / links and POST forms with CSRF | — |

Filters on the search page are a GET form; sort tabs and applied-filter pills are links built with the `qs_replace` / `qs_toggle` tags so every filter state is a shareable URL.

## Template tags and context

`apps/core/templatetags/fa.py` is registered as a **builtin** (`TEMPLATES[...]["builtins"]`), so no `{% load %}` is needed.

| Tag / filter | Purpose |
|---|---|
| `{{ n\|fa }}` | Latin → Persian digits |
| `{{ n\|price }}` | `1250000` → `۱٬۲۵۰٬۰۰۰` |
| `{{ phone\|phone }}` | `09123456789` → `۰۹۱۲ ۳۴۵ ۶۷۸۹` |
| `{{ dt\|ago }}` | Divar-style relative time (`هم‌اکنون`, `۲ ساعت پیش`, `دیروز`, … then a Jalali date) |
| `{{ dt\|jalali:"%d %B %Y" }}`, `\|jmonth`, `\|hm`, `\|chat_time`, `\|days_left` | Jalali formatting helpers |
| `{% jalali_year %}` | Current Jalali year (footer copyright) |
| `{{ listing\|pct_off }}` | "% cheaper than new" from `Listing.percent_off` |
| `{% qs_replace key=value … %}` | Current querystring with keys replaced/removed, `page` dropped |
| `{% qs_toggle key value %}` | Toggle one value in a multi-valued param |
| `\|in_list`, `\|get_item`, `\|add_str` | Small template conveniences |

`apps/core/context_processors.site` adds to every template: `SITE_NAME`, `SITE_URL`, `CONTACT_PHONE`, `CONTACT_EMAIL`, `MODERATION_SLA_HOURS`, `NEW_ACCOUNT_LISTING_CAP`, `nav_categories` (root categories), `cities`, `current_city` (from `session["city"]`, default first active city) and `unread_chat_count` (header badge).

## Static and media pipeline

- **Static**: WhiteNoise serves `static/` (collected to `staticfiles/` in production with the compressed-manifest storage). Fonts, CSS, vendored JS and the favicon are all local; there is no foreign CDN in the page.
- **Media**: uploads go through `apps/core/images.py`: size limit 12 MB, Pillow decode, EXIF auto-orient, then two WebP variants per `settings.IMAGE_SIZES` — `gallery` (1200×900 max) stored on `ListingImage.image` and `thumb` (480×360 max) on `ListingImage.thumb`. Originals are not kept. Processing is synchronous in the request (no queue at this scale).
- **Storage backend**: `FileSystemStorage` under `MEDIA_ROOT` by default; setting `S3_BUCKET` switches `STORAGES["default"]` to django-storages S3 (Arvan-compatible) — see [integrations.md](integrations.md).
- In `DEBUG`, `config/urls.py` serves `/media/` from Django; in production the web server or CDN must serve it.

## Cache and rate limiting

The Django cache (`LocMemCache` by default, Redis when `REDIS_URL` is set) is used as a lightweight counter store:

| Key | Limit | Where |
|---|---|---|
| `otp-rate:{phone}` | `OTP_RATE_LIMIT_PER_HOUR` (5) sends per hour | `apps/accounts/views._rate_limited` |
| `otp-last:{phone}` | last code issued (console backend only; used by tests) | `apps/accounts/sms.ConsoleBackend` |
| `reveal:{user_id}` | 30 phone reveals per hour | `apps/listings/views.reveal_phone` |

Listing view counts are deduplicated per session with `session["seen"]` (last 200 codes), not the cache. Note that `LocMemCache` is per-process: with several gunicorn workers the limits are per-worker until Redis is configured.

## Settings and environment

`config/settings.py` reads everything through `env(key, default, cast)`; `.env.example` lists every knob. Principles:

- Defaults make a fresh clone runnable with no services (`SQLite`, `SMS_BACKEND=console`, `PAYMENT_GATEWAY=fake`, local media, locmem cache).
- Production flips on with `DEBUG=false` (secure cookies, HSTS, proxy SSL header), `DATABASE_URL`, `REDIS_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SITE_URL`.
- Product constants are settings, not code: `LISTING_TTL_DAYS` (30), `NEW_ACCOUNT_LISTING_CAP` (5), `LISTING_MAX_IMAGES` (8), `MODERATION_MODEL`, `MODERATION_SLA_HOURS` (2), `OTP_TTL_SECONDS` (120), `OTP_LENGTH` (5), `OTP_DEV_CODE` (dev only).

## URL map

All routes are named; templates never hard-code paths (the one exception is the panel's login redirect, `/login/?next=`).

**accounts** (`app_name="accounts"`, mounted at `/`)

| Name | Path | Purpose |
|---|---|---|
| `login` | `login/` | Phone form → issues OTP, stores phone in session |
| `verify` | `login/verify/` | 5-digit code; creates the user on first login |
| `resend` | `login/resend/` | POST; re-issues a code (rate-limited) |
| `logout` | `logout/` | POST |
| `profile` | `me/` | Tabs: active / pending / sold / saved / account |
| `account_edit` | `me/account/` | POST; display name, city, district, notify toggles |
| `saved_search_delete` | `me/saved-search/<pk>/delete/` | POST |
| `set_city` | `set-city/` | POST; writes `session["city"]` |
| `public_profile` | `u/<pk>/` | Seller page with their live listings |

**listings** (`app_name="listings"`, mounted at `/`)

| Name | Path | Purpose |
|---|---|---|
| `home` | `/` | Hero stats, categories, age/brand chips, latest 12 |
| `search` | `s/` | Filtered browse; `?cat=` also accepted |
| `category` | `s/<category_slug>/` | Same view, category from path (SEO URL) |
| `category_district` | `s/<category_slug>/<district_slug>/` | Same view, district pinned |
| `detail` | `v/<code>/<slug>/` | Listing page; wrong slug → permanent redirect |
| `detail_short` | `v/<code>/` | Same without slug |
| `reveal` | `v/<code>/reveal/` | POST (htmx) phone reveal |
| `save` | `v/<code>/save/` | POST toggle |
| `report` | `v/<code>/report/` | POST; also accepts `conversation=<pk>` from chat |
| `mark_sold`, `renew`, `delete`, `edit` | `v/<code>/…/` | Owner (or staff) actions |
| `post` | `new/` | Create wizard |
| `upload_image`, `delete_image` | `new/upload/`, `new/image/<pk>/delete/` | Edit-flow image endpoints |
| `save_search` | `save-search/` | POST |
| `page` | `p/<slug>/` | Static pages: about, posting-guide, safety, terms, privacy, faq |

Route order matters: the action routes are declared before `v/<code>/<slug>/` because slugs use the `str` converter (Persian slugs don't match Django's `slug` converter).

**chat** (`/chat/`): `inbox`, `start/<code>/`, `<pk>/` (`thread`), `<pk>/messages/` (polling fragment), `<pk>/send/`, `<pk>/feedback/`.

**panel** (`app_name="panel"`, `/panel/`): `queue`, `listing/<pk>/approve/`, `listing/<pk>/reject/`, `reports/`, `reports/<pk>/resolve/`, `users/`, `users/<pk>/`, `users/<pk>/ban/`, `listings/`, `listings/<pk>/takedown/`, `stats/`, `decisions/`. All guarded by `operator_required` (staff only).

**payments** (`/pay/`): `plans/`, `start/<plan_id>/`, `callback/`, `fake/<pk>/`, `<pk>/result/`.

**root**: `admin/`, `sitemap.xml`, `robots.txt`, `manifest.webmanifest`, `sw.js`.

## Where to add a new …

- **Page**: view in the owning app's `views.py`, name it in that app's `urls.py`, template under `templates/<app>/` extending `base.html`; use the design-system classes ([frontend.md](frontend.md)).
- **htmx fragment**: a `_name.html` template rendered when `request.htmx` is true; keep the full-page path working without JS.
- **Filter on search**: read it in `_apply_filters`, add a pill in `search()`, add the control to `templates/listings/search.html`; document the query param in [search-and-seo.md](search-and-seo.md).
- **Auto-check**: append a flag dict in `apps/listings/services.run_auto_checks`; if the operator checklist should reflect it, map its code in `apps/moderation/services.checklist_for`.
- **Listing type**: it is already on the schema (`Listing.Type`); add it to `Listing.ENABLED_TYPES` and remove the `is-soon` treatment in `post.html`.
- **SMS provider / payment gateway / storage**: see [integrations.md](integrations.md).
- **Model field**: edit the model, `manage.py makemigrations`, and update `seed_demo` if the demo data should exercise it.
