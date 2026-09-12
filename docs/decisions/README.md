# Architecture decision records

Short records of the decisions that shape this codebase and would be expensive to reverse. Each one states the situation at the time, what was decided, and what that costs or enables. Decisions taken by stakeholders live in the planning repo; the records here are the engineering choices made on top of those defaults.

Related: [../architecture.md](../architecture.md) · [../roadmap.md](../roadmap.md) · planning docs in `../../../wonderkidz-planning/`

## Index

| # | Decision | Status |
|---|---|---|
| [0001](0001-django-server-rendered-htmx.md) | Django with server-rendered templates, HTMX and Alpine instead of an SPA | accepted |
| [0002](0002-reuse-mockup-css.md) | Reuse the mockup CSS design system instead of Tailwind | accepted |
| [0003](0003-sqlite-and-local-disk-defaults.md) | SQLite and local disk by default; Postgres, Redis and S3 via environment | accepted |
| [0004](0004-plug-and-play-integrations.md) | External services behind env-selected backends (SMS, payments, storage) | accepted |
| [0005](0005-full-listing-type-schema-sell-only-ui.md) | Full listing-type schema, sell-only UI | accepted |
| [0006](0006-moderation-defaults.md) | Moderation default `ai_first`, 30-day listing TTL, 5-listing cap | accepted |
| [0007](0007-unicode-slugs-and-code-urls.md) | Unicode slugs with `str` URL converters; code-first listing URLs | accepted |

## Adding a record

Copy the template below into `NNNN-short-title.md` with the next number, add a row to the index, and link it from the doc it affects. Never edit an accepted record's decision; supersede it with a new one and mark the old one `superseded by NNNN`.

```markdown
# NNNN — Title

**Status:** proposed | accepted | superseded by NNNN · **Date:** YYYY-MM-DD

## Context
What situation forced a choice, and which constraints applied.

## Decision
What was chosen, in one or two sentences, then the specifics.

## Consequences
What becomes easier, what becomes harder, what must be revisited and when.
```
