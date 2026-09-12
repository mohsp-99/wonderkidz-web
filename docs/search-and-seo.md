# Search and SEO

Search is deliberately simple at launch: a normalised text column queried with `icontains` plus structured filters, on a few thousand rows. SEO is structural: every category, district and listing is a real server-rendered URL with a title, description, canonical link and product markup, and the long-tail "category × age × district" pages are the compounding asset a general board never builds.

Related: [architecture.md](architecture.md) · [data-model.md](data-model.md) · [frontend.md](frontend.md)

## Search implementation (`apps/listings/views.search`)

**Base set:** LIVE listings in the current city (`City.get_current(request)` — the header pill, session-backed). Listings in inactive cities are never shown.

**Text query `q`:** `apps.core.text.normalize(q)` is split on whitespace and each word becomes `search_text__icontains=word` — words are ANDed, order-independent, substring matched. `search_text` is rebuilt on every `Listing.save()` from title, description, category name, root category name, district name and brand name, normalised the same way (ي/ی and ك/ک unified, diacritics stripped, digits Latinised, ZWNJ → space, lower-cased). So «لگو» finds «LEGO»? No — Latin brand names match only Latin queries; Persian brand aliases would need to be added to the brand name or `search_text`.

**Query parameters**

| Param | Values | Filter |
|---|---|---|
| `q` | text | AND of normalised words on `search_text` |
| `cat` | category slug (or path `/s/<slug>/`) | `category_id in category.descendant_ids()` |
| `age` (multi) | `0-1`, `1-3`, `3-5`, `5-8`, `8+` | `age_range in` |
| `cond` (multi) | `new`, `likenew`, `used`, `repair` | `condition in` |
| `complete` | `1` | `is_complete=True, missing_parts=False` |
| `box` | `1` | `has_box=True` |
| `min`, `max` | toman, Persian or Latin digits, separators allowed | `price >= / <=` (`parse_int`) |
| `brand` (multi) | brand slug | `brand__slug in` |
| `dist` (multi) | district slug (or path `/s/<cat>/<dist>/`) | `district__slug in` |
| `photo` | `1` | has at least one image |
| `official` | `1` | `owner.account_type == official` |
| `verified` | `1` | `owner.is_verified` |
| `chat` | `1` | `allow_chat` |
| `sort` | `newest` (default), `cheapest`, `expensive`, `nearest` | see below |
| `page` | int | 24 per page |

Unknown values are ignored, not errored. Every filter state is a plain GET URL, so results are shareable and crawlable.

**Sorting** (`_apply_sort`): `newest` and the default order by `-is_promoted, -published_at` (paid promotion floats first); `cheapest` / `expensive` by price then recency; `nearest` puts the logged-in user's own district first (`Case/When` on `district_id`) and otherwise behaves like newest — there is no geo distance in v1.

**Pagination and infinite scroll:** `Paginator(qs, 24)`. The full page renders `templates/listings/search.html`; when the request is htmx **and** carries `page=`, the view returns only `templates/listings/_results.html` (the card grid plus the next «آگهی‌های بیشتر» button, which is an `hx-get` with `hx-swap="outerHTML"` on itself). Without JavaScript the same button is a normal link and `partials/pagination.html` provides prev/next.

**Facets:** counts next to condition, brand and district checkboxes come from the city-wide live set (`base`), not from the currently filtered set — cheap and predictable, but a count may exceed what the combined filters return. Applied filters render as removable pills built with `qs_replace` / `qs_toggle` (`page` is always dropped). The sidebar also shows the category median price (`services.median_price`) as «میانگین قیمت این دسته».

**Saved searches:** «ذخیرهٔ این جستجو» POSTs the current querystring to `listings:save_search` (login required) and stores a `SavedSearch`; there is no matching/notification job yet.

## SEO surfaces

| Surface | Where | Notes |
|---|---|---|
| Category pages | `/s/<category-slug>/` | Title «{category}، {city} \| وندرکیدز»; breadcrumb; the sidebar tree links root → children |
| Category × district pages | `/s/<category-slug>/<district-slug>/` | District pinned via the path; title «{category}، {district}» |
| Category × age | `/s/<slug>/?age=3-5` | Query-string only; title adds the age label when exactly one is selected |
| Listing pages | `/v/<code>/<slug>/` | Slug is the Persian title (`str` converter); a stale slug 301s to the current one; `/v/<code>/` also resolves |
| Home | `/` | Hero, category tiles with live counts, latest listings |
| Static pages | `/p/about/`, `/p/posting-guide/`, `/p/safety/`, `/p/terms/`, `/p/privacy/`, `/p/faq/` | Templates under `templates/listings/pages/`; terms and privacy are marked as drafts |
| Seller pages | `/u/<pk>/` | Live listings of one seller |

Per page: `<title>` and `meta description` blocks, `<link rel="canonical">` built from `SITE_URL + request.path` (query-string variants canonicalise to the path), `theme-color`, manifest. Listing pages add JSON-LD `Product` (name, description, up to 4 image URLs, brand, `itemCondition`, `Offer` with price in IRR, availability, url) — note the price is emitted as the toman number with `priceCurrency: IRR`; switch to `× 10` if rich results should show rial.

**Sitemap** (`/sitemap.xml`, `apps/listings/sitemaps.py`): static routes (home, search), every `Category`, every LIVE `Listing` with `lastmod = updated_at`. Category × district combinations are not enumerated yet.

**robots.txt**: disallows `/admin/`, `/panel/`, `/chat/`, `/me/`, `/login/`, `/pay/`; points to the sitemap.

**Non-live listings** return 404 to strangers (owners and staff can still open them), so sold and removed pages drop out of the index naturally; consider a "sold" page with related listings later to keep the URL's equity.

## Long-tail landing pages

The planning docs' bet: "wooden toys for 2-year-olds in Saadat Abad" is a page, not a filter state. What exists today:

- Category and category × district are path-addressable and in the breadcrumb/sidebar, so they get internal links.
- Age and brand are query parameters; they render correct titles but are not linked as canonical pages and not in the sitemap.

To extend: add routes such as `s/<cat>/<dist>/<age>/` (or `s/<cat>/age-<age>/`) that pin the parameters the same way `category_district` does, generate `seo_title` / `seo_description` per combination (the `Category.seo_*` fields are the hook), add them to the sitemap only when the combination has enough live listings (say ≥ 5) so thin pages aren't indexed, and link them from the category page ("همین دسته برای ۱ تا ۳ سال در پونک"). Keep the current-city session behaviour in mind: crawlers have no session, so path-based pages must resolve the city from the district, not from the session.

## Upgrade path

- **Postgres trigram**: on Postgres, add a `GinIndex(OpClass("search_text", "gin_trgm_ops"))` and switch the word loop to `TrigramSimilarity` / `__trigram_similar` for typo tolerance; the write-time normalisation already does the hard part. SQLite has no equivalent, which is why the launch query is plain `icontains`.
- **Meilisearch** (planned when listings reach tens of thousands): index `search_text`, the structured fields and `published_at`, keep Django as the source of truth, and swap `_apply_filters` for a Meilisearch query behind the same view and query parameters so URLs and templates don't change.
- **Facets intersected with filters** and **geo "nearest"** (district adjacency table or lat/lng on districts) are view-level changes; the query-parameter contract above should stay stable so saved searches keep working.
