# Frontend

The UI is the stakeholder mockups made real: `static/css/styles.css` is the mockup design system copied verbatim ("Warm Teal & Amber" — teal for brand and trust, amber for the one loud action), templates reuse the mockup markup and Persian copy, and behaviour comes from a small vanilla-JS file plus HTMX and Alpine. Persian, RTL, mobile-first, no build step, no foreign CDN.

Related: [architecture.md](architecture.md) · [search-and-seo.md](search-and-seo.md)

## Files

| File | Role |
|---|---|
| `static/css/styles.css` | Design system from `wonderkidz-planning/ui-mockups/styles.css`, plus a `@font-face` for the self-hosted Vazirmatn variable font prepended at the top. Edit only to fix mockup-level bugs; put app-specific rules in `app.css`. |
| `static/css/app.css` | Additions the mockups didn't need: real `<img>` inside placeholders, active header link, htmx indicators, form error styling, upload-slot overlays, `.pager`, `.sort-tabs a`, `min-width: 0` guards on grid columns. |
| `static/js/app.js` | Ported from the mockup `shared.js`; see "Behaviours". |
| `static/js/htmx.min.js`, `static/js/alpine.min.js` | Vendored (htmx 2.0, Alpine 3.14), loaded `defer` from `base.html`. |
| `static/fonts/Vazirmatn[wght].woff2` | Variable weight 100–900. |
| `static/img/favicon.svg` | Teal rounded square with the 🧸 mark. |
| `templates/base.html` | `<html lang="fa" dir="rtl">`, meta/canonical/manifest, CSS, scripts, `hx-headers` with the CSRF token on `<body>`, flash messages, header/footer includes. Blocks: `title`, `meta_description`, `head_extra`, `body_class`, `header`, `content`, `footer`, `scripts`. |
| `templates/partials/header.html`, `footer.html` | Site chrome; header shows city pill, search, chat badge (`unread_chat_count`), «ثبت آگهی». |
| `templates/partials/card.html` | The listing card; include with `{% include "partials/card.html" with listing=obj %}`. |
| `templates/panel/base_panel.html` | Operator chrome (`body.adm`, `.adm-hd`), overrides `header`/`footer`. |
| `templates/accounts/_auth_header.html`, `_auth_footer.html` | Minimal chrome for login/verify. |

## Design tokens

Defined on `:root` in `styles.css` §1: `--teal-50…900` (brand), `--amber-50…700` (action), semantic `--green/blue/red/violet-600/100`, warm neutrals `--ink`, `--ink-2…4`, `--line`, `--line-2`, `--surface`, `--surface-2`, `--bg`; radii `--r-xs…xl`, `--r-pill`; shadows `--sh-1…3`; `--maxw: 1220px`; `--font` (Vazirmatn with system fallbacks). Use the tokens, never raw hex, in `app.css` and inline styles.

## Component classes (by `styles.css` section)

| Section | Classes | Purpose |
|---|---|---|
| Buttons | `.btn` + `.btn-primary` (teal), `.btn-action` (amber — reserved for «ثبت آگهی» and chat CTA), `.btn-ghost`, `.btn-soft`, `.btn-quiet`, `.btn-danger`, sizes `.btn-sm` / `.btn-lg`, `.btn-block`, state `.is-disabled` | all clickable actions |
| Form controls | `.input`, `.select`, `.textarea`, `.field`, `.label`, `.req`, `.hint`, `.check`, `.toggle-row` + `.switch`, `.input-suffix` + `.sfx`, `.otp-inputs` | forms; add `.is-invalid` (app.css) on error |
| Chips & badges | `.chip` (+ `.is-on`), `.chips-row`, `.chips-scroll`; `.badge-new`, `.badge-likenew`, `.badge-used`, `.badge-repair` (condition), `.badge-live`, `.badge-pending`, `.badge-sold` (status), `.badge-official`, `.badge-verified`, `.badge-soon` | filters, listing states, trust marks |
| Header | `.hd`, `.hd-in`, `.logo` / `.logo-mark` / `.logo-txt`, `.city-pill`, `.hd-search` + `.si`, `.hd-actions`, `.hd-link` (+ `.is-secondary`, `.is-here`), `.hd-burger`, `.hd-mob` (+ `.is-open`) | site chrome |
| Footer | `.ft`, `.ft-in`, `.ft-about`, `.ft-badges` / `.ft-seal`, `.ft-contact`, `.ft-social`, `.ft-bottom` | |
| Placeholders | `.ph` + gradient `.ph-a` … `.ph-h`, `.ph-count` («۱/۴» pill), `.ph-tag` (+ `.t-green`) | image frame with 4:3 ratio; see "Image convention" |
| Listing card | `.card`, `.card-body`, `.card-title`, `.card-tags`, `.card-micro`, `.card-price`, `.card-meta`, `.chat-i`; `.grid-cards` (responsive grid), `.rail` (horizontal scroll) | browse surfaces |
| Generic blocks | `.panel` (+ `.panel-pad`), `.notice` + `.notice-info/-green/-warn/-red` with `.ni` icon, `.tabs` / `.tab` / `.tabpane` (+ `.is-on`, `.cnt`), `.crumb` + `.sepc`, `.empty` + `.e-icon`, `.avatar` (+ `.official`), `.sec` / `.sec-head` / `.sec-sub` / `.more`, `.wrap`, `.wrap-narrow`, `.num` | layout and messaging |
| Home | `.hero`, `.hero-stats`, `.cat-grid` / `.cat-tile` / `.cat-ic` / `.cat-n` / `.cat-c`, `.green-strip` + `.gs-item`, `.how-grid` / `.how-step` / `.hs-n` | |
| Search | `.search-layout`, `.filters` (+ `.is-open` drawer on mobile) / `.fl-head` / `.fl-group` / `.fl-tree` / `.clear`, `.c-count`, `.price-row`, `.results-bar`, `.sort-tabs`, `.rb-count`, `.applied` + `.pill`, `.filter-fab`, `.drawer-only`, `.scrim` | |
| Listing detail | `.detail-layout`, `.gallery` / `.gal-thumbs` / `.gt`, `.dt-title`, `.dt-meta`, `.dt-price`, `.dt-orig`, `.attr-table`, `.safety-list` / `.sl-i`, `.contact-box`, `.seller-card`, `.contact-actions`, `.phone-reveal` (+ `.is-on`) / `.pn`, `.sticky-bar` (with `body.has-sticky`) | |
| Post flow | `.stepper` / `.st-item` (+ `.is-on`, `.is-done`) / `.st-num` / `.st-lbl` / `.st-line`, `.steppane` (+ `.is-on`), `.step-nav`, `.type-grid` / `.type-card` (+ `.is-on`, `.is-soon`), `.cat-pick`, `.form-2col`, `.upload-grid` / `.up-slot` (+ `.filled`) / `.cover-tag`, `.photo-check`, `.preview-2` | |
| Chat | `.chat-layout`, `.chat-list` / `.chat-list-head` / `.chat-items`, `.ci` (+ `.is-on`) / `.ci-thumb` / `.ci-body` / `.ci-top` / `.ci-name` / `.ci-time` / `.ci-sub` / `.ci-last` / `.ci-unread`, `.chat-thread`, `.ct-head`, `.ct-safety`, `.ct-msgs`, `.msg` (+ `.me`, `.them`, `.msg-sys`) / `.msg-b` / `.msg-t`, `.msg-day`, `.ct-compose` | |
| Auth | `.auth-wrap`, `.auth-card`, `.authpane`, `.auth-foot`, `.otp-inputs` | |
| Profile | `.pf-head`, `.pf-stats`, `.ml-row` / `.ml-thumb` / `.ml-body` / `.ml-title` / `.ml-meta` / `.ml-actions` | |
| Admin | `body.adm`, `.adm-hd` (+ `nav a.is-on`, `.tagm`, `.who`), `.stat-row` / `.stat` (+ `.alert`) / `.s-l` / `.s-v` / `.s-d` (+ `.up`, `.flat`), `.q-item` (+ `.flagged`) / `.q-thumb` / `.q-fields` / `.q-side` / `.q-check`, `.reject-box` (+ `.is-on`), `.adm-table` | operator panel |
| Responsive | breakpoints at 1024 / 860 / 600 px: filters become a drawer, detail and chat layouts stack, `.sticky-bar` appears, header search wraps | |

Section 19 (`.en*`, the English presentation hub) is unused by the app and can be deleted when the CSS is next touched.

## Image convention

Cards, galleries, thumbnails and admin rows all use the same frame:

```html
<div class="ph {{ listing.ph_class }}{% if listing.cover %} has-img{% endif %}">
  {% if listing.cover %}<img src="{{ listing.cover.thumb_url }}" alt="{{ listing.title }}" loading="lazy">{% endif %}
  <span aria-hidden="true">{{ listing.emoji }}</span>
  <span class="ph-count num">۱/{{ listing.image_count|fa }}</span>
</div>
```

Without an image the category's gradient (`ph_class`) and emoji show — the mockup's "no external images anywhere" look; with an image, `app.css` makes the `<img>` fill the frame and hides the emoji and dot pattern. Gallery pages use `image.url` (1200 px), everything else `thumb_url` (480 px).

## Behaviours in `static/js/app.js`

| Init | What it does |
|---|---|
| `initBurger` | toggles `.hd-mob.is-open` |
| `initCity` | opens/closes `#city-panel`; the options are POST forms to `accounts:set_city` |
| `initTabs` | `[data-tabgroup]` + `[data-tab=paneId]` buttons switch `.tabpane.is-on`; syncs `location.hash` so redirects like `/me/#t-pending` open the right tab |
| `initDrawer` | mobile filter drawer (`[data-filters]`, `[data-openfilters]`, `[data-closefilters]`, Escape, scrim) |
| `initGallery` | `[data-gal=url]` thumbs swap the `img` in `[data-galmain]` and the «n/N» count |
| `initOtp` | 5 single-digit boxes: auto-advance, backspace, paste of a full code, Persian digit normalisation into hidden `#otp-code`, enables `#otp-submit` and auto-submits when complete; countdown from `#otp-timer[data-seconds]`, then reveals `#otp-resend` |
| `initPhoneMask` | `[data-phone-input]` keeps digits only; `[data-numeric]` (prices) re-formats as `۱٬۲۵۰٬۰۰۰` while typing (server parses with `parse_int`) |
| `initCopy` | `[data-copy=text]` buttons copy to clipboard with «کپی شد ✓» feedback |
| `initChatScroll` | scrolls `.ct-msgs` to the bottom on load and after every htmx swap |
| service worker | registered only on `https:` |

Alpine is used where state is page-local: the post wizard (`postForm(cats, dists)` defined inline in `post.html`: current step, chosen root/child category, condition chip, image previews, live preview card), and small booleans for inline report / reject forms. htmx handles anything that needs the server ([architecture.md](architecture.md) → rendering table).

## Persian and RTL conventions

- Digits: never print Latin digits in prose; pipe through `fa` / `price` / `phone` / `ago` and wrap in `.num` for tabular figures.
- Prices: `۱٬۲۵۰٬۰۰۰ <small>تومان</small>` via the `price` filter; the numeric input shows the same format while typing.
- Dates: Jalali everywhere (`jalali`, `jmonth`, `hm`, `chat_time`); weeks start on Saturday in stats.
- Phone numbers, emails, codes: `dir="ltr"` on the element so the RTL bidi algorithm doesn't reorder them.
- ZWNJ (`‌`) is part of correct Persian spelling in copy («می‌شود», «آگهی‌ها»); keep it in templates, and remember the search normaliser turns it into a space.
- Copy tone: warm, parent-facing, the reuse story visible but not preachy; take strings from the mockups verbatim when one exists.
- Emoji are used as icons throughout (from the mockups). They need a colour-emoji font on the viewing machine; headless Linux without one renders boxes, real browsers are fine.

## Fonts and PWA

- Vazirmatn is self-hosted (variable font, `font-display: swap`); the mockups' Google Fonts link was removed so no request leaves the country.
- `templates/manifest.webmanifest` (RTL, standalone, teal theme) and `templates/sw.js` (cache-first for `/static/` only) give installability on phones; both are served by `TemplateView` so they can use Django context if needed.

## Adding a page that looks right

1. Find the closest mockup in `wonderkidz-planning/ui-mockups/` and copy its markup structure and class names.
2. Extend `base.html` (or `panel/base_panel.html` for operator pages); set `title` and `meta_description` blocks.
3. Wrap content in `.wrap` (or `.wrap-narrow`), group into `.panel.panel-pad` or `.sec` blocks, use `.notice-*` for messages and `.btn-*` variants as above — amber only for the primary conversion action.
4. Render numbers and dates through the filters; add `.num` to numeric spans.
5. If the page lists listings, include `partials/card.html`; if it needs a partial update, add a `_fragment.html` and an htmx attribute rather than JavaScript.
6. Check both widths: 1280 px and 390 px (the drawer/sticky-bar breakpoints live in `styles.css` §20).
