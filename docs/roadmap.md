# Roadmap

What comes after the sell-only MVP, grouped by horizon and drawn from the planning docs (proposal §6 "out of scope for v1", pivot brief §7, tech-stack doc) and from gaps found while building. Each item carries a readiness tag: **schema-ready** (no database change), **needs migration** (model change), **needs infra** (a service or account outside the app). Nothing here is scheduled; order within a horizon is a suggestion.

Related: [decisions/](decisions/README.md) · [architecture.md](architecture.md) · [operations.md](operations.md) · [deployment.md](deployment.md)

## Before launch (blocking or near-blocking)

| Item | Why | Readiness | Notes |
|---|---|---|---|
| Real SMS and payment credentials | nobody can log in with the `console` backend | needs infra | Kavenegar + SMS.ir fallback, Zarinpal + IDPay backup; templates need provider approval. First live transaction on each provider must be verified by hand. |
| Chat message retention job | UI and privacy page promise 6-month retention; nothing enforces it | schema-ready | management command deleting `chat.Message` older than 180 days where no open report references the conversation; schedule with `expire_listings`. |
| Unify promoted-flag lapse | `services.expire_listings` does not clear `is_promoted` after `promoted_until` | schema-ready | move the fallback logic from the command into the service. |
| Monitoring stack | tech-stack doc: GlitchTip, Uptime Kuma, Umami/Plausible | needs infra | add `sentry-sdk` with DSN from env; a `/healthz` view; analytics tag behind an env flag. |
| Backups + restore drill | no automation in repo | needs infra | nightly `pg_dump` to a second-region bucket, 30-day retention. |
| Legacy URL redirects | keep the old wonderkidz.net SEO footprint | needs infra | mapping table in [deployment.md](deployment.md); implement at CDN/proxy. |
| enamad + Search Console | trust badge is a conversion factor; sitemap submission | needs infra | footer already has a placeholder seal. |
| Terms and privacy review | pages exist as drafts marked "پیش‌نویس" | schema-ready | legal review of `templates/listings/pages/terms.html`, `privacy.html`. |

## Soon after launch (weeks)

| Item | Why | Readiness | Notes |
|---|---|---|---|
| Saved-search SMS dispatch | `SavedSearch` rows are stored and shown; no notifications go out | schema-ready | nightly job: re-run each saved querystring, SMS new matches to users with `notify_saved_search`. Needs a "last notified" timestamp → needs migration if you want dedupe. |
| Promoted listings ("نردبان") | first revenue line per stakeholder default (post-MVP) | schema-ready | set `Plan(kind=promote).is_active=True`; the fake→real gateway is a config switch; ordering already honours `is_promoted`. Add a "promote" button on the profile row. |
| Professional-seller label | allowed, labelled, same limits (stakeholder default) | schema-ready | `User.account_type = pro` exists; needs a badge on cards and an application flow (currently only via a BADGE plan or admin). |
| Facet counts that respect active filters | sidebar counts are computed on the city-wide live set | schema-ready | compute per-facet counts on the filtered queryset minus that facet. |
| Type-specific error rendering in the wizard | posting a disabled listing type shows only a generic error | schema-ready | render `form.type.errors` in the Alpine step 1. |
| Operator quality-of-life | bulk approve, keyboard shortcuts, image zoom in the queue | schema-ready | panel templates only. |
| OTP hygiene | `OTPCode` rows accumulate | schema-ready | periodic delete of rows older than a day. |

## Next quarter

| Item | Why | Readiness | Notes |
|---|---|---|---|
| Real-time chat (SSE or WebSocket) | polling every 4 s is fine at launch volume; latency and load improve later | needs infra | same endpoints; Django Channels or an SSE view behind Redis pub/sub. No user-visible change except latency. |
| Image classifier for child faces | the "no photos of children" rule is enforced by eye today | needs infra | plug into `run_auto_checks` as a `child_photo` flag; run in a background worker (django-rq, Redis already present). |
| Background job queue | image processing, SMS dispatch and sweeps run inline or via cron | needs infra | django-rq worker service in compose; move `process_upload` and notifications off the request path. |
| Other listing types (free, donate, looking-for, swap, rent) | schema carries all six; UI ships sell | schema-ready | extend `Listing.ENABLED_TYPES`, make price optional per type, type-aware copy on cards/detail, wanted-type without images. See [decisions/0005](decisions/0005-full-listing-type-schema-sell-only-ui.md). |
| Subscription plans | "no fee at launch; schema supports plans" | schema-ready | `Plan(kind=subscription)`; current effect is `listing_cap += 20`; define real entitlements. |
| Trigram / Meilisearch search | `icontains` on `search_text` is instant at thousands of listings; typo tolerance and ranking come later | needs infra (Meilisearch) or needs migration (`pg_trgm` index) | the search view is the single swap point. |
| Long-tail landing pages | proposal §3: "wooden toys for 2-year-olds in Saadat Abad" as a page | schema-ready | category × district routes exist (`/s/<cat>/<district>/`); add age and brand as path segments with generated titles/descriptions and sitemap entries. |
| Seller ratings / deal feedback surfaced | `Conversation.buyer_feedback`/`seller_feedback` are recorded but not shown | schema-ready | aggregate on the public profile. |

## Later (6–12 months)

| Item | Why | Readiness | Notes |
|---|---|---|---|
| Expansion beyond Tehran | city is a field, not a constant | schema-ready | activate a `City`, add districts, seed a launch stock; city selector already in the header. Trigger per stakeholder default: when a search reliably returns nearby results. |
| Neshan map view / distance sort | "nearest" today means the user's own district first | needs migration (coordinates on `District` or listing) + needs infra (Neshan API) | |
| Native app | roughly doubles the project; web/PWA first | needs infra | add DRF JSON API next to the templates; auth reuses OTP. |
| Escrow / safe payment | only if fraud appears (report-and-ban stance) | needs migration | the behavioural signals (reports, price flags, mass contacts) are the trigger to revisit. |
| Community / well-being content | 12-month vision | needs migration | profiles and listings are designed to carry more content types; new models, not rewrites. |
| Legacy account migration | default is a fresh start with outreach | needs migration | only if stakeholders reverse the default. |

## Deliberately not planned

- Delivery or logistics of any kind.
- Dispute mediation between users.
- A separate API/frontend split or microservices.
