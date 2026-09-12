# Glossary

Persian product terms as they appear in the UI, with their English meaning and the identifier used in code. Use this when reading templates, writing copy, or naming things: the Persian is what users and operators see, the English is what the code says. Copy comes from the planning mockups and should be reused verbatim.

Related: [data-model.md](data-model.md) · [moderation.md](moderation.md) · [frontend.md](frontend.md)

## Product and roles

| Persian | English | Code |
|---|---|---|
| وندرکیدز | WonderKidz (the platform) | `settings.SITE_NAME` |
| تابلوی آگهی | classifieds board | — |
| آگهی | listing | `listings.Listing` |
| کد آگهی | listing code (six digits, immutable) | `Listing.code` |
| ثبت آگهی | post a listing | `listings:post`, `/new/` |
| آگهی‌های من | my listings (profile) | `accounts:profile`, `/me/` |
| والد | parent (a personal account) | `User.AccountType.PARENT` = `parent` |
| والد تأییدشده | verified parent (phone verified) | `User.is_verified` |
| فروشندهٔ حرفه‌ای | professional seller (toy shop) | `User.AccountType.PRO` = `pro` |
| فروشگاه وندرکیدز / حساب رسمی | the official WonderKidz store account (first-party inventory) | `User.AccountType.OFFICIAL` = `official`, `User.is_official` |
| اپراتور | operator (moderator) | `User.is_staff`, `/panel/` |
| مدیر | admin / superuser | `User.is_superuser`, `/admin/` |
| خریدار / فروشنده | buyer / seller | `Conversation.buyer` / `Conversation.seller`, `Listing.owner` |
| نام نمایشی | display name | `User.display_name` |
| شمارهٔ موبایل | mobile number (the identity) | `User.phone`, format `09xxxxxxxxx` |
| کد تأیید / کد یک‌بارمصرف | OTP code | `accounts.OTPCode`, `OTP_LENGTH` |
| مسدود | banned | `User.is_banned`, `User.ban_reason` |
| اخطار | warning (to a user) | `User.warnings_count`, `ModerationDecision.Decision.WARN` |
| سقف آگهی فعال | active-listing cap | `User.listing_cap`, `NEW_ACCOUNT_LISTING_CAP` |

## Location

| Persian | English | Code |
|---|---|---|
| شهر | city | `catalog.City` (`is_active` false shows «به‌زودی») |
| محله | district / neighbourhood | `catalog.District` |
| سعادت‌آباد، شهرک غرب، پونک | the three launch districts | slugs `saadat-abad`, `shahrak-gharb`, `punak` |
| محل پیشنهادی تحویل | suggested meetup place | `Listing.meetup_hint` |
| نزدیک‌ترین | nearest (sort) | `sort=nearest` (user's district first) |

## Catalogue and attributes

| Persian | English | Code |
|---|---|---|
| دسته‌بندی | category | `catalog.Category` (two levels: root › child) |
| برند | brand | `catalog.Brand` |
| بدون برند / دست‌ساز | no brand / handmade | a `Brand` row |
| ردهٔ سنی | age range | `Listing.age_range`, `AgeRange`: `0-1`, `1-3`, `3-5`, `5-8`, `8+` |
| وضعیت کالا | condition | `Listing.condition`, `Listing.Condition` |
| نو | new | `new` |
| در حد نو | like new (< 6 months use) | `likenew` |
| کارکردهٔ سالم | used, working | `used` |
| نیاز به تعمیر | needs repair | `repair` |
| کامل بودن | completeness | `Listing.is_complete`, `has_box`, `has_manual`, `has_battery`, `missing_parts`; `Listing.completeness_text` |
| همهٔ قطعات موجود است | all parts present | `is_complete` |
| جعبهٔ اصلی / دفترچهٔ راهنما | original box / manual | `has_box` / `has_manual` |
| یادداشت بهداشتی | hygiene note (required) | `Listing.hygiene_note` |
| شست‌وشو شده | washed | copy inside `hygiene_note`; `ph-tag t-green` on cards |
| قیمت پیشنهادی | asking price (toman) | `Listing.price` |
| قیمت نو در بازار | new retail price | `Listing.original_price`; `Listing.percent_off` → «٪ ارزان‌تر» |
| قابل مذاکره | negotiable | `Listing.is_negotiable` |
| تومان | toman (currency unit; gateways take rial = ×10) | `price` filter |
| نوع آگهی | listing type | `Listing.type`, `Listing.Type` |
| فروش / رایگان / اهدا به خیریه / دنبالش می‌گردم / معاوضه / اجارهٔ نفر به نفر | sell / free / donate / wanted / swap / peer rent | `sell` / `free` / `donate` / `wanted` / `swap` / `rent`; only `sell` in `ENABLED_TYPES` |
| به‌زودی | coming soon | `badge-soon`; disabled types, inactive cities |
| چک‌لیست عکس وضعیت | condition-photo checklist | copy in the post wizard, step 4 |
| عکس اصلی | cover photo | `Listing.cover` (first `ListingImage` by `order`) |

## Listing lifecycle

| Persian | English | Code (`Listing.Status`) |
|---|---|---|
| پیش‌نویس | draft | `draft` |
| در انتظار تأیید / در صف بررسی | pending review | `pending`; `submitted_at` |
| منتشر شده | live | `live`; `published_at`, `expires_at` |
| رد شد | rejected | `rejected`; `reject_reason`, `reject_note` |
| متوقف | paused | `paused` |
| فروخته شد | sold | `sold`; `sold_at` |
| منقضی | expired | `expired`; set by `expire_listings` |
| حذف‌شده | removed (by user or takedown) | `removed` |
| تمدید | renew (fresh 30 days) | `Listing.renew()`, `listings:renew` |
| اصلاح و ارسال دوباره | fix and resubmit | edit a rejected listing → `submit_listing` |
| بازدید | views | `Listing.views_count` |

## Contact

| Persian | English | Code |
|---|---|---|
| اطلاعات تماس / نمایش شماره | phone reveal | `listings:reveal`, `listings.PhoneReveal`, `Listing.reveals_count`, `Listing.allow_phone` |
| چت | in-app chat | `chat.Conversation`, `chat.Message`, `Listing.allow_chat` |
| گفت‌وگو | conversation | `chat.Conversation` |
| پیام سیستمی | system message | `Message.is_system` (sender null) |
| خوانده‌نشده | unread | `Message.is_read`, `unread_chat_count` |
| معامله انجام شد؟ | did the deal happen? (feedback) | `Conversation.buyer_feedback` / `seller_feedback` = `good` / `bad` |
| ذخیره | save (bookmark a listing) | `listings.SavedListing`, `listings:save` |
| جستجوی ذخیره‌شده | saved search | `accounts.SavedSearch` |

## Trust and moderation

| Persian | English | Code |
|---|---|---|
| بررسی / صف بررسی | review / review queue | `panel:queue` |
| مدل بررسی | moderation model | `MODERATION_MODEL`: `ai_first`, `pre_approval`, `post_review` |
| هشدار خودکار | automatic flag | `Listing.auto_flags` (list of `{code, level, text}`), `run_auto_checks` |
| بدون هشدار | no flags | empty `auto_flags` |
| تأیید و انتشار | approve and publish | `panel:approve` → `Listing.publish()`, `Decision.APPROVE` |
| رد کردن / دلیل رد | reject / reject reason | `panel:reject` → `Listing.reject()`, `Decision.REJECT` |
| گزارش | report | `listings.Report`, `listings:report` |
| مشکوک به کلاهبرداری | suspected scam (deposit request) | `Report.Reason.SCAM` |
| وضعیت واقعی با آگهی نمی‌خواند | condition mismatch | `Report.Reason.MISMATCH` |
| کالای ممنوعه یا ناایمن | prohibited or unsafe item | `Report.Reason.PROHIBITED` |
| عکس کودک | photo of a child (banned) | `Report.Reason.CHILD_PHOTO`; flag code `child_photo` |
| پیام توهین‌آمیز | abusive message | `Report.Reason.ABUSE` |
| فوری / متوسط / کم | urgent / normal / low priority | `Report.Priority` |
| بی‌اشکال | dismissed (no issue) | `Report.Status.DISMISSED`, `Decision.DISMISS` |
| حذف آگهی + مسدودسازی | takedown and ban | `Decision.TAKEDOWN` + `Decision.BAN` |
| تذکر به فروشنده | warn the seller | `Decision.WARN` |
| تصمیم‌ها | decisions log | `moderation.ModerationDecision`, `panel:decisions` |
| SLA («تا ۲ ساعت») | review SLA | `MODERATION_SLA_HOURS` |
| بیعانه | deposit (the scam pattern) | copy in safety notices |
| نکات ایمنی | safety tips (per category) | `Category.safety_tips`, `Category.tips()` |

## Money and plans

| Persian | English | Code |
|---|---|---|
| نردبان / آگهی ویژه | promote / featured listing | `Plan.Kind.PROMOTE`, `Listing.is_promoted`, `promoted_until` |
| اشتراک فروشنده | seller subscription | `Plan.Kind.SUBSCRIPTION` |
| نشان فروشنده | seller badge | `Plan.Kind.BADGE` |
| پلن | plan | `payments.Plan` (`is_active` false at launch) |
| پرداخت / درگاه | payment / gateway | `payments.Payment`, `PAYMENT_GATEWAY`: `fake`, `zarinpal`, `idpay` |
| کد پیگیری | reference id | `Payment.ref_id` |

## UI vocabulary (design system classes)

| Persian | English | Class |
|---|---|---|
| کارت آگهی | listing card | `.card`, `templates/partials/card.html` |
| جای عکس | photo placeholder | `.ph`, `.ph-a` … `.ph-h`, `Category.ph_class` |
| نشان | badge | `.badge-new`, `-likenew`, `-used`, `-repair`, `-live`, `-pending`, `-sold`, `-verified`, `-official`, `-soon` |
| چیپ | chip (filter pill) | `.chip`, `.chip.is-on` |
| اعلان | notice box | `.notice-info`, `-green`, `-warn`, `-red` |
| کشوی فیلتر | filter drawer (mobile) | `[data-filters]`, `.scrim` |
| مراحل ثبت آگهی | post-wizard stepper | `.stepper`, `.st-item`, `.steppane` |
| پنل مدیریت | operator panel | `body.adm`, `.adm-hd`, `.q-item`, `.stat` |
