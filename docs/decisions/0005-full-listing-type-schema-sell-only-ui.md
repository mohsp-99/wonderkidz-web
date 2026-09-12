# 0005 — Full listing-type schema, sell-only UI

**Status:** accepted · **Date:** 2026-09-12

## Context

Stakeholders settled on sell-only listings for the MVP but left free, donate, looking-for, swap and user-to-user rent as open decisions. The stakeholder-questions default is "schema supports all; UI ships sell", with the explicit note that the listing schema and category pages should be built to accommodate every type so later types are a UI change, not a rebuild. Subscription plans and promoted listings are likewise "no fee at launch, schema ready".

## Decision

`Listing.type` is a `TextChoices` column with all six values; `Listing.ENABLED_TYPES = [SELL]` gates what the post form accepts, and the wizard renders the other five as disabled "به‌زودی" cards. `price` is nullable so non-priced types fit. Category-specific extras are meant for `Listing.attributes` (JSON, currently unused by the form) rather than new columns. `payments.Plan` and `payments.Payment` exist with `is_active=False` plans seeded; `Listing.is_promoted` / `promoted_until` already influence ordering. `City` is a table with an `is_active` flag, and every listing carries both city and district, so expansion beyond Tehran needs no rewrite.

## Consequences

- Turning on a listing type is: add it to `ENABLED_TYPES`, adjust form validation (price optional for free/donate, "wanted" has no images requirement), and decide how the type shows on cards. No migration.
- Turning on a fee is: mark a plan active and choose a gateway. No migration.
- The search view, cards and detail page assume `type == sell` in copy ("قیمت پیشنهادی فروشنده"); those strings need type-aware variants when new types ship.
- Carrying unused columns and choices is a small, deliberate cost.
