# Moderation

Moderation is a core function of the board, not an afterthought: every listing passes automatic checks on submission, a switchable review model decides whether a human sees it before it goes live, and one operator works the queue, user reports and takedowns from the panel at `/panel/`. The stance is **report-and-ban, no mediation** — WonderKidz never arbitrates a money dispute between users; it restricts the offending account.

Related: [data-model.md](data-model.md) · [architecture.md](architecture.md) · [operations.md](operations.md)

## Review models (`MODERATION_MODEL`)

`apps/listings/services.submit_listing(listing)` runs the auto-checks, stores them on `listing.auto_flags`, then routes by `settings.MODERATION_MODEL`:

| Value | Clean listing (no flags) | Warn-level flags | Block-level flag | Default |
|---|---|---|---|---|
| `ai_first` | published immediately (`publish()`) | → PENDING for the operator | → PENDING | **yes** |
| `pre_approval` | → PENDING | → PENDING | → PENDING | |
| `post_review` | published immediately; flags stay visible in the panel's listings view | published immediately | → PENDING | |

The same function runs on **edit** when the listing was REJECTED or DRAFT, or when a LIVE listing's `title`, `description`, `price`, `category`, `hygiene_note` or `condition` changed (`REVIEW_FIELDS` in `apps/listings/views.py`). Image-only or toggle-only edits do not trigger re-review. The seller sees either «ثبت و منتشر شد» or «در صف بررسی است و تا حداکثر ۲ ساعت دیگر منتشر می‌شود» accordingly.

`submitted_at` is set in all paths so the panel can compute approval time.

## Automatic checks

`apps/listings/services.run_auto_checks(listing)` returns a list of `{"code", "level", "text"}`. Level `block` always forces human review regardless of model; `warn` only matters under `ai_first`.

| Code | Level | Trigger | Text shown to the operator |
|---|---|---|---|
| `contact_in_text` | warn | `apps.core.text.has_contact_info(title + description)`: phone numbers, `+98`, URLs, `www.`, `@handle`, `t.me/`, «تلگرام», «اینستاگرام» | «شماره تماس یا لینک در متن آگهی دیده می‌شود.» |
| `banned_item` | **block** | normalised text contains one of `BANNED_KEYWORDS`: «صندلی خودرو», «کارسیت», «لباس», «شیر خشک», «پوشک» | «کالای خارج از حوزهٔ اسباب‌بازی یا ممنوعه: «…».» |
| `price_outlier` | warn | `price < 25 %` of the median live price in the category (root: all descendants; child: itself) via `median_price()` | «قیمت بسیار پایین‌تر از میانگین دسته … الگوی رایج کلاهبرداری «بیعانه بگیر و غیب شو».» |
| `hygiene_missing` | warn | `hygiene_note` empty or shorter than 8 characters (the form already requires ≥ 8, so this mainly catches admin-created rows) | «یادداشت بهداشتی خالی یا بسیار کوتاه است.» |
| `single_image` | warn | listing has ≤ 1 image | «فقط یک عکس دارد.» |
| `new_account` | warn | owner joined < 2 days ago and this is their first listing | «حساب تازه (کمتر از ۲ روز عضویت) و اولین آگهی.» |

The form itself rejects contact info in title/description outright (`ListingForm.clean_title/clean_description`), so `contact_in_text` fires only on text that slipped past the regex differently or on admin-created listings.

**Not automated:** there is no image classifier. The child-photo rule («عکس کودکان ممنوع است») is enforced by the seller's attestation checkbox (`attested_safe`, required) and the operator's eyes; the panel checklist shows it as «عکس کودک ندارد (بررسی چشمی)» ⚠️ unless a `child_photo` flag exists (which no current check produces — it is reserved for a future classifier). The seed data fabricates such a flag on one listing to demonstrate the UI.

## The operator panel

Access: `operator_required` in `apps/moderation/views.py` — anonymous → `/login/?next=…`, logged-in non-staff → home with «این بخش فقط برای اپراتورهای وندرکیدز است.». Grant access by setting `is_staff` on the user (Django admin or `createsuperuser`).

Every page shows the stat row from `services.panel_stats()`: live count (+ this week), pending count with oldest wait and SLA, open reports with urgent count, contacts this week (new conversations + phone reveals), new users (7 d), average approval time (7 d, `reviewed_at − submitted_at`), decisions today.

### صف بررسی — queue (`panel:queue`)

PENDING listings ordered by `submitted_at`. Each `.q-item` shows seller (verified, listing count, sold count), price, category, district, age, condition, image count, hygiene note, every auto flag as a notice, the description, image thumbnails and a checklist derived from the flags (`services.checklist_for`).

| Action | DB effect | SMS (if `owner.notify_moderation`) |
|---|---|---|
| **تأیید و انتشار** (`panel:approve`) | `listing.publish(by=operator)` → LIVE, `expires_at = now + 30 d`; `ModerationDecision(approve)` | «وندرکیدز: آگهی «…» تأیید و منتشر شد.» |
| **رد کردن** (`panel:reject`, reason + optional note) | `listing.reject(reason, note, by)` → REJECTED; `ModerationDecision(reject)` | «وندرکیدز: آگهی «…» تأیید نشد. دلیل: … — note. می‌توانید آگهی را اصلاح و دوباره ارسال کنید.» |

Both are htmx POSTs that replace the action slot with a badge; a second click on an already-reviewed item returns «قبلاً بررسی شده».

Reject reasons (`services.REJECT_REASONS`): «در عکس‌ها چهرهٔ کودک دیده می‌شود», «عکس نامفهوم یا بی‌کیفیت است», «دسته‌بندی اشتباه است», «کالای خارج از حوزهٔ اسباب‌بازی», «کالای ناایمن یا فراخوان‌شده», «شماره تماس یا لینک در متن آگهی», «قیمت غیرواقعی / مشکوک به کلاهبرداری», «یادداشت بهداشتی خالی است», «عکس ناکافی», «متن دیگر…». The seller sees reason and note on their profile's pending tab with an «اصلاح و ارسال دوباره» button.

### گزارش‌ها — reports (`panel:reports`)

Open reports (`?status=open`, default) or handled ones, ordered by priority then time, with a count of open reports on the same target. Actions (`panel:resolve_report`, `action=`):

| Action | Label | Effect |
|---|---|---|
| `takedown_ban` | «حذف آگهی + مسدودسازی» | `takedown_listing` + `ban_user(owner)`; report RESOLVED |
| `takedown` | «حذف آگهی» | listing → REMOVED, decision `takedown`, SMS «آگهی … به دلیل «…» حذف شد.» |
| `warn` | «تذکر به فروشنده» (listing) / «اخطار به کاربر» (chat: the party who is not the reporter) | `warnings_count += 1`, decision `warn`, SMS «وندرکیدز: تذکر — …» |
| `dismiss` | «بی‌اشکال» | report DISMISSED, decision `dismiss` |

Report reasons and priorities are on the `Report` model ([data-model.md](data-model.md)); listing reports for scam / child photo / prohibited items are created as **urgent** by `apps/listings/views.report`. Chat reports post to the same endpoint with `conversation=<pk>`.

### کاربران — users (`panel:users`, `panel:user_detail`, `panel:ban_user`)

Search by phone or display name, filter `?f=banned` / `?f=staff`. The detail page lists the user's listings (with takedown buttons), reports about them, decisions concerning them, conversation and reveal counts, and the ban toggle.

**Ban semantics** (`services.ban_user`): `is_banned = True`, `ban_reason` stored, every LIVE and PENDING listing of theirs → REMOVED, decision `ban`, SMS «حساب شما به دلیل نقض قوانین مسدود شد.». A banned user cannot complete OTP login («این حساب مسدود شده است.»), cannot post, cannot start a chat. Unban clears the flag and logs a `dismiss` decision with reason «رفع مسدودی»; removed listings are **not** restored. Superusers and the operator themselves cannot be banned from the panel.

### آگهی‌ها — listings (`panel:listings`, `panel:takedown`)

All listings with status chips and counts, search by title / code / owner phone. Takedown works on any status and always notifies the owner (no opt-out — it is a policy action, not a courtesy).

### آمار — stats (`panel:stats`)

Listings per status, weekly series (8 weeks, weeks start Saturday) for signups, conversations, reveals and publishes, top categories and districts by live listings, total and verified users. Plain tables; no charting library.

### تصمیم‌ها — decisions (`panel:decisions`)

Today's `ModerationDecision` rows plus the previous 7 days, with approve/reject counts for today.

## Django admin vs the panel

The panel is the operator's daily tool. Django admin (`/admin/`, superusers) remains for reference data (cities, districts, categories, brands, plans), user field edits, and bulk listing actions (`approve` / `reject` actions on `ListingAdmin` — note these bypass the decision log and SMS; prefer the panel).

## Constants

| Setting | Default | Used for |
|---|---|---|
| `MODERATION_MODEL` | `ai_first` | routing above |
| `MODERATION_SLA_HOURS` | 2 | seller-facing promise («تا حداکثر ۲ ساعت») and the panel's SLA label |
| `NEW_ACCOUNT_LISTING_CAP` | 5 | `User.listing_cap` default; LIVE + PENDING count against it |
| `LISTING_TTL_DAYS` | 30 | expiry set on publish/renew |
| `LISTING_MIN_IMAGES` / `LISTING_MAX_IMAGES` | 1 / 8 | form validation |
