# Testing

How the test suite is organised and run, what it covers, the conventions for adding tests, and a recipe for visual checks with headless Chrome. The suite is plain `django.test.TestCase` on SQLite, 133 tests, about 15 seconds.

Related: [operations.md](operations.md) · [deployment.md](deployment.md) (CI) · [architecture.md](architecture.md)

## Running

```bash
scripts/wk test                                   # ruff → makemigrations --check → full suite
scripts/wk test tests.test_listings               # one module
scripts/wk test tests.test_listings.SearchTests   # one class
scripts/wk test tests.test_chat.ChatTests.test_start_creates_conversation   # one test
.venv/bin/python manage.py test --noinput -v 2    # without the wrapper, verbose
.venv/bin/ruff check .                            # lint only
```

Tests run with the normal `config.settings` (`DEBUG` may be true; it does not matter). Django creates a throwaway SQLite database per run. The `.env` on the machine is loaded, but every test class that touches settings-sensitive code is wrapped in `media_settings` (below), which pins the values that matter.

## Layout

| File | Lines | Covers |
|---|---|---|
| `tests/utils.py` | 146 | factories and the shared `media_settings` override |
| `tests/test_core.py` | 95 | `apps/core/text.py` (digits, `normalize`, `parse_int`, `format_price`, `clean_phone`, `mask_phone`, `has_contact_info`), `apps/core/dates.py` (`ago`, Jalali), template filters and the `qs_replace`/`qs_toggle` tags |
| `tests/test_accounts.py` | 270 | OTP login/verify/resend, rate limit, expiry, `OTP_DEV_CODE`, banned users, logout, safe `next`, profile tabs, account edit (district must belong to city), `set_city`, public profile, `UserManager`, the three SMS backends with `requests` mocked |
| `tests/test_listings.py` | 584 | post wizard (JPEG → WebP + thumb, contact-info rejection, attestation, image limits, invalid file, cap, ban, disabled type), `run_auto_checks` incl. median outlier and banned keywords, all three `MODERATION_MODEL` values, search filters/sort/normalization/category routes/applied pills/facets/htmx fragment, save-search, home, static pages, sitemap/robots, detail (JSON-LD, slug redirect, per-session views, visibility), reveal (anon `HX-Redirect`, dedupe, `allow_phone=False`, rate limit), save, report priorities, owner actions, edit re-review rules, image upload/delete |
| `tests/test_chat.py` | 142 | start (system message, self-chat refused), participant-only access, send, read marking, `unread_chat_count`, feedback, sold listing hides compose |
| `tests/test_panel.py` | 196 | access gating, queue listing, approve/reject with `ModerationDecision`, report actions (takedown + ban, dismiss), ban removes live listings, stats/decisions/users/listings pages |
| `tests/test_payments.py` | 186 | `FakeGateway` end to end (start → fake page → callback → PAID + promote; cancel), plans page, `ZarinpalGateway`/`IdpayGateway` start and verify with `requests.post` mocked, callback views |
| `tests/test_seed.py` | 70 | `seed_demo` creates listings with images, second run is a no-op, `expire_listings` command |

### `tests/utils.py`

- `media_settings`: an `override_settings` that points `MEDIA_ROOT` at a temp directory (so `media/` in the repo is never touched), forces `FileSystemStorage`, plain `StaticFilesStorage`, `OTP_DEV_CODE=""`, `SMS_BACKEND="console"`, `PAYMENT_GATEWAY="fake"`, `MODERATION_MODEL="ai_first"` and a dedicated LocMem cache. Decorate every class that uploads images, logs in, or reads those settings.
- Factories: `make_city`, `make_district`, `make_category`, `make_brand`, `make_user`, `make_staff`, `make_listing`, `add_image` (generates a PIL image and runs it through `apps.core.images.process_upload`), `upload_file` (an in-memory JPEG as `SimpleUploadedFile`), `listing_post_data` (a valid wizard POST body to tweak per test). They use `get_or_create` with stable slugs, so calling them twice returns the same row.

## Conventions for new tests

- One module per app; one `TestCase` class per feature area; test names read as sentences (`test_edit_with_price_change_returns_to_pending`).
- Build state with the factories, never with the seed command (except in `test_seed.py`); the seed is slow and its content will drift.
- Log in with `self.client.force_login(user)` unless the test is about the OTP flow.
- For htmx endpoints send `HTTP_HX_REQUEST="true"` and assert on the fragment; for anonymous htmx calls assert the `HX-Redirect` header.
- Mock network with `unittest.mock.patch("requests.post")`; no test may reach the internet.
- A found bug gets a failing test first, marked `# BUG:` with `@unittest.expectedFailure` until fixed, so the suite stays green and the bug stays visible.
- Persian in assertions is fine (`assertContains(resp, "در انتظار تأیید")`); normalise digits with `apps.core.text.to_en_digits` when comparing numbers.
- Keep the whole suite under about 90 seconds; anything slower belongs behind a flag.

## Lint

`ruff` is configured in `pyproject.toml`: line length 120, target py310, rules `E, F, W, I` with `E501` ignored, `migrations/`, `.venv/`, `staticfiles/`, `media/` excluded. `ruff check --fix .` sorts imports. Ruff is not in `requirements.txt`; `scripts/wk setup` and CI install it separately.

## CI

`.github/workflows/ci.yml` runs on pushes to `main` and on pull requests: install → `ruff check .` → `manage.py check` → `makemigrations --check --dry-run` → `manage.py test --noinput`, on Python 3.12 with `OTP_DEV_CODE=12345`. A failing lint or a missing migration fails the build. On `main` a second job builds the Docker image (not pushed). See [deployment.md](deployment.md).

## Visual checks with headless Chrome

The mockups in `../wonderkidz-planning/ui-mockups/` are the visual reference. To compare a page:

```bash
scripts/wk start                                   # server on :8000
google-chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
  --window-size=1280,1700 --screenshot=/tmp/home.png http://127.0.0.1:8000/
google-chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
  --window-size=390,1600 --screenshot=/tmp/home-mobile.png http://127.0.0.1:8000/
# the mockup, for side-by-side comparison
google-chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
  --window-size=1280,1700 --screenshot=/tmp/mock-home.png \
  file://$PWD/../wonderkidz-planning/ui-mockups/home.html
```

Headless Chrome has no session, so for logged-in pages (post wizard, profile, chat, panel) render the HTML with the Django test client, rewrite asset URLs to the running server, and screenshot the file:

```python
# .venv/bin/python - <<'EOF'   (run from the repo root)
import os, re, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"; django.setup()
from django.conf import settings; settings.ALLOWED_HOSTS = ["*"]
from django.test import Client
from apps.accounts.models import User

c = Client(); c.force_login(User.objects.get(phone="09120000000"))
for name, url in {"panel": "/panel/", "post": "/new/", "profile": "/me/"}.items():
    html = c.get(url, follow=True).content.decode()
    html = re.sub(r'(href|src)="/(static|media)/', r'\1="http://127.0.0.1:8000/\2/', html)
    open(f"/tmp/{name}.html", "w").write(html)
# EOF
google-chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
  --window-size=1280,1900 --screenshot=/tmp/panel.png file:///tmp/panel.html
```

Two known artifacts of this setup: emoji render as boxes unless a colour-emoji font is installed (`fonts-noto-color-emoji`), and narrow RTL screenshots are clipped on the right edge exactly as the mockups are, so compare against the mockup capture rather than against the viewport.
