# 0006 — Moderation default `ai_first`, 30-day listing TTL, 5-listing cap

**Status:** accepted · **Date:** 2026-09-12

## Context

The moderation model was a stakeholder decision with three options: human pre-approval of everything, live-then-review, or automatic check first with humans only on flags. The documented default is the third. The mockups promise sellers "live within 2 hours", show a review queue that highlights flagged items, cap new accounts at 5 active listings, and expire listings after 30 days with a renew button. No image classifier or LLM was available at build time.

## Decision

- `MODERATION_MODEL` setting with three values, applied in `apps/listings/services.py::submit_listing`: `ai_first` (default) publishes immediately when `run_auto_checks` returns no flags and queues otherwise; `pre_approval` always queues; `post_review` always publishes and keeps the flags visible in the panel.
- `run_auto_checks` is rule-based, not ML: contact details in text, banned keywords (block-level), price below 25 % of the category median, weak hygiene note, a single photo, brand-new account. Flags are stored on the listing as `auto_flags` and rendered as notices and a checklist in the queue. Child-face detection is a ⚠️ "check by eye" line, not a classifier.
- `LISTING_TTL_DAYS=30`, `NEW_ACCOUNT_LISTING_CAP=5` (per-user `listing_cap`, raised by admins or by a subscription plan), `MODERATION_SLA_HOURS=2` shown in the UI.
- Edits to a live listing that change text or price go back through review.

## Consequences

- With the default, most clean listings from established accounts go live instantly; the operator's queue contains only flagged items and new sellers, which keeps the SLA credible with one part-time operator.
- The rules are transparent and cheap to tune (thresholds live in `services.py`), but they cannot see images; a photo classifier is a roadmap item and slots into `run_auto_checks`.
- Switching to human pre-approval for launch week is a one-line config change.
- The 25 % price threshold needs enough live listings per category to compute a median; on a sparse board it never fires, which is safe.
