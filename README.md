# WonderKidz Web

The WonderKidz classifieds platform — a buy/sell board for kids' toys on the Divar model, scoped to one vertical. Parents post structured listings (age range, condition, completeness, brand, original price); buyers search, filter, and contact the seller by phone reveal or in-app chat. The platform does not handle delivery or payment between users; what it sells is trust and structure: verified parent accounts, moderated listings, and category pages a general board never builds. Persian, RTL, mobile-first, server-rendered.

Planning, research, and the UI mockups this build follows live in the separate [wonderkidz-planning](https://github.com/mohsp-99/wonderkidz-planning) repo. Where a stakeholder answer was missing, the documented default applies.

## Quick start

```bash
scripts/wk setup     # venv, dependencies, .env, migrations, demo seed
scripts/wk start     # background dev server on http://localhost:8000
```

Log in with any phone number and OTP `12345`. Operator account `09120000000` opens the moderation panel at `/panel/`. Full walkthrough: [docs/getting-started.md](docs/getting-started.md).

## Stack

Django 5.1 · Django templates + HTMX + Alpine.js · the mockup design system as plain CSS with self-hosted Vazirmatn · SQLite for local dev, PostgreSQL in production · Redis optional · Pillow image pipeline (WebP) · WhiteNoise · Docker + GitHub Actions.

SMS/OTP (console, Kavenegar, SMS.ir), payment gateways (fake, Zarinpal, IDPay) and media storage (local, Arvan S3) are plug-and-play backends selected by environment variables. Nothing in the critical path depends on a service that blocks Iran.

## Documentation

Everything else is in [`docs/`](docs/README.md):

| | |
|---|---|
| [Getting started](docs/getting-started.md) | run it, log in, try the flows |
| [Architecture](docs/architecture.md) · [Data model](docs/data-model.md) · [Frontend](docs/frontend.md) · [Search & SEO](docs/search-and-seo.md) | how it is built |
| [Moderation](docs/moderation.md) · [Integrations](docs/integrations.md) · [Glossary](docs/glossary.md) | how it behaves |
| [Deployment](docs/deployment.md) · [Operations](docs/operations.md) · [Testing](docs/testing.md) | how it runs |
| [Decisions](docs/decisions/README.md) · [Roadmap](docs/roadmap.md) | why, and what next |

AI-assisted sessions start from [CLAUDE.md](CLAUDE.md).

## Development

```bash
scripts/wk test           # ruff + migration check + test suite
scripts/wk seed --flush   # reset demo data
scripts/wk manage <cmd>   # any manage.py command
```

## License

Proprietary — © WonderKidz. All rights reserved.
