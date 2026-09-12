# CLAUDE.md — working on wonderkidz-web

WonderKidz is a Persian, RTL, server-rendered classifieds board for second-hand kids' toys (the Divar model, one vertical). This file is the orientation for AI-assisted sessions. Human-facing docs live in `docs/` — read `docs/README.md` first when a task touches an area you don't know.

## What this repo is

- Django 5.1 monolith, one deployable unit: `config/` + `apps/{core,accounts,catalog,listings,chat,moderation,payments}`.
- Templates + HTMX + Alpine.js, no build step, no SPA. The design system is `static/css/styles.css`, copied verbatim from the mockups in the sibling `wonderkidz-planning` repo (`ui-mockups/`). New UI must reuse its classes; add only small overrides in `static/css/app.css`.
- Product decisions come from the planning repo (`wonderkidz-pivot-brief`, `wonderkidz-proposal`, `wonderkidz-stakeholder-questions` — the "Default" column is what we build when nobody answers). Rationale for build-level choices is in `docs/decisions/`.

## Commands

```bash
scripts/wk setup        # venv, deps, .env, migrate, first seed
scripts/wk start|stop|status|logs|restart   # background dev server on :8000 (WK_PORT to change)
scripts/wk test         # ruff + makemigrations --check + full test suite (~15 s, 130+ tests)
scripts/wk seed --flush # reset demo data
scripts/wk manage <cmd> # any manage.py command
```

Login in dev: any phone, OTP `12345` (`OTP_DEV_CODE` in `.env`). Operator: `09120000000` (admin password `admin`, panel at `/panel/`).

## Conventions that matter

- **Persian copy is product, not decoration.** Reuse strings from the mockups verbatim; keep tone warm and non-preachy. Digits go through the `fa` filter, prices through `price`, phones through `phone` (with `dir="ltr"`), times through `ago`/`jalali`/`hm`. These are builtin template tags (`apps/core/templatetags/fa.py`), no `{% load %}` needed.
- **URLs are named and namespaced** (`listings:detail`, `accounts:login`, `chat:thread`, `panel:queue`, `payments:start`). Slugs are unicode, so routes use `<str:...>` converters and the code-first listing URL `/v/<code>/<slug>/`; keep action routes (`/v/<code>/edit/`) registered before the slug route.
- **Models are the contract.** Listing lifecycle moves only via `submit()/publish()/reject()/mark_sold()/renew()` and `apps.listings.services.submit_listing` (which applies `MODERATION_MODEL`). Don't set `status` by hand in views.
- **Integrations are pluggable** via env: `SMS_BACKEND` (`apps/accounts/sms.py`), `PAYMENT_GATEWAY` (`apps/payments/gateways.py`), `S3_BUCKET` (settings). Never call a provider directly from a view; go through the backend interface. Network calls never raise into views.
- **HTMX endpoints** return fragments when `request.htmx` is true and a full page/redirect otherwise; keep both paths working (progressive enhancement). CSRF header is injected globally in `base.html`.
- **Search** reads `Listing.search_text` (normalized in `apps/core/text.py`); if you add searchable fields, update `Listing.refresh_search_text`.
- **Images** always go through `apps/core/images.py` (WebP gallery + thumb). Never store originals.
- Python 3.10-compatible syntax (the local venv is 3.10, Docker is 3.12). Ruff config in `pyproject.toml`; CI fails on lint, on un-generated migrations, and on tests.

## Before you change things

- Run `scripts/wk test` before and after. Add tests in `tests/` using the factories in `tests/utils.py`.
- Model changes need a migration in the same commit (`scripts/wk manage makemigrations <app>`), and a note in `docs/data-model.md`.
- New env vars: add to `config/settings.py` via `env()`, to `.env.example`, and to `docs/integrations.md` or `docs/deployment.md`.
- New pages: extend `base.html`, port the closest mockup, keep it crawlable (real HTML, not JS-only), add the route to `docs/architecture.md`'s URL map.
- Don't commit `.env`, `db.sqlite3`, `media/`, `.run/`, `staticfiles/`.
- Commit only when asked. Commit messages: what and why, in English.

## Environment quirks (this machine)

- pip is configured with an Iranian mirror that 404s on some wheels; `scripts/wk setup` falls back to `https://pypi.org/simple`.
- No `jq`, no `unzip`; use Python. `sudo` needs an interactive password.
- Headless Chrome is available (`google-chrome --headless=new --screenshot=...`) but has no color-emoji font, so emoji render as boxes in screenshots only.
- When automating with shell tools, avoid `pkill -f <pattern>` — it can match the wrapper shell. Use `scripts/wk stop`.

## Map

| Need | Look at |
|---|---|
| How a request flows, URL map, where to add X | `docs/architecture.md` |
| Models and the listing state machine | `docs/data-model.md` |
| Moderation models, auto-checks, panel actions | `docs/moderation.md` |
| SMS, payments, storage backends | `docs/integrations.md` |
| Design system, RTL rules, JS behaviours | `docs/frontend.md` |
| Search, filters, SEO surfaces | `docs/search-and-seo.md` |
| Deploying, env vars, CI | `docs/deployment.md` |
| Runbook, commands, backups, troubleshooting | `docs/operations.md` |
| Tests and screenshots | `docs/testing.md` |
| Why we chose X | `docs/decisions/` |
| What's next | `docs/roadmap.md` |
