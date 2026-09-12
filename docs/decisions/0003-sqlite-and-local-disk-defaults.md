# 0003 — SQLite and local disk by default; Postgres, Redis and S3 via environment

**Status:** accepted · **Date:** 2026-09-12

## Context

The target production stack is PostgreSQL 16, Redis and Arvan object storage (tech-stack doc §5). None of those existed on the developer machine or in CI at build time, the hosting accounts were still in phase 0, and the instruction was to produce a working version that runs immediately. The search plan (`pg_trgm` at launch) also depended on Postgres.

## Decision

`config/settings.py` chooses everything from the environment with local defaults:

- `DATABASES` from `DATABASE_URL` via `dj-database-url`, default `sqlite:///db.sqlite3`.
- `CACHES` is Redis when `REDIS_URL` is set, otherwise LocMem.
- Media storage is `FileSystemStorage` unless `S3_BUCKET` is set, in which case `django-storages` S3 with the endpoint/keys from `S3_*` and `MEDIA_URL` from `S3_PUBLIC_URL`.
- Static files always go through WhiteNoise, so no web server configuration is needed anywhere.

Search uses a normalised `search_text` column (Persian normalisation in `apps/core/text.py`) with `icontains` per word, which works identically on SQLite and Postgres. The `pg_trgm` index is deferred until listing volume needs it.

## Consequences

- `scripts/wk setup && scripts/wk start` gives a full working site with demo data in under a minute; CI needs no services.
- `docker-compose.yml` exercises the production shape (Postgres + Redis) locally.
- Rate limits and caches are per-process without Redis; any multi-worker deployment must set `REDIS_URL`.
- Trigram/typo-tolerant search and Meilisearch remain roadmap items; the search view is the single place to swap them in.
- SQLite-specific behaviour (no `DISTINCT ON`, weaker concurrency) must not leak into code; tests run on SQLite, so anything Postgres-only needs an explicit test skip.
