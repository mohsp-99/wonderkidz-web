# 0007 — Unicode slugs with `str` URL converters; code-first listing URLs

**Status:** accepted · **Date:** 2026-09-12

## Context

Listing titles, category names and district names are Persian. The planning docs ask for "clean Persian-friendly slugs" for SEO. Django's `SlugField(allow_unicode=True)` stores Persian slugs fine, but the `<slug:…>` URL converter only matches ASCII, so `get_absolute_url()` for any Persian title raised `NoReverseMatch` in the first integration pass. Listings also need a stable identifier that survives title edits, and the mockups show a six-digit "کد آگهی".

## Decision

- Listing URLs are `/v/<code>/<slug>/` where `code` is a random six-digit `Listing.code` (unique, immutable) and `slug` is derived from the title with `slugify(allow_unicode=True)`. The view resolves by `code` only; a stale or missing slug redirects to the canonical URL, and `/v/<code>/` is a short form.
- Category and district routes are `/s/<category_slug>/` and `/s/<category_slug>/<district_slug>/`.
- All of these use the `str` converter, and in `apps/listings/urls.py` the action routes (`reveal/`, `save/`, `report/`, `sold/`, `renew/`, `delete/`, `edit/`) are registered **before** the slug route so `/v/<code>/edit/` is not swallowed by `/v/<code>/<slug>/`.
- Reference data seeded by `seed_demo` uses ASCII slugs (`building`, `saadat-abad`) for readability, but the routing works for either.

## Consequences

- Persian titles produce readable, shareable URLs; renaming a listing never breaks links.
- Route order in `apps/listings/urls.py` is load-bearing; adding a new `/v/<code>/<action>/` route must go above the slug route. A test covers the detail redirect.
- `str` matches anything without a slash, so unknown categories must 404 explicitly in the view (they do).
- Percent-encoded Persian in logs and analytics is ugly but correct; sitemaps emit the encoded form.
