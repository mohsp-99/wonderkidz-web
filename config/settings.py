"""
WonderKidz — Django settings.

Everything environment-specific comes from env vars (see .env.example).
Defaults are chosen so `manage.py migrate && manage.py seed_demo && manage.py runserver`
works out of the box on SQLite with console OTP and a fake payment gateway.
"""
import mimetypes
import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(key, default=None, cast=str):
    val = os.environ.get(key)
    if val is None or val == "":
        return default
    if cast is bool:
        return val.lower() in ("1", "true", "yes", "on")
    if cast is int:
        return int(val)
    if cast is list:
        return [v.strip() for v in val.split(",") if v.strip()]
    return val


SECRET_KEY = env("SECRET_KEY", "dev-insecure-change-me")
DEBUG = env("DEBUG", True, bool)
ALLOWED_HOSTS = env("ALLOWED_HOSTS", ["*"] if DEBUG else [], list)
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS", [], list)
# Platform convenience: Render sets RENDER_EXTERNAL_HOSTNAME on every service; use it for SITE_URL when unset.
_platform_host = env("RENDER_EXTERNAL_HOSTNAME")
SITE_URL = env("SITE_URL", f"https://{_platform_host}" if _platform_host else "http://localhost:8000")
SITE_NAME = "وندرکیدز"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.humanize",
    "apps.core",
    "apps.accounts",
    "apps.catalog",
    "apps.listings",
    "apps.chat",
    "apps.moderation",
    "apps.payments",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
            ],
            "builtins": ["apps.core.templatetags.fa"],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# DATA_DIR: one writable directory for everything that must survive a restart when there is no external
# database/object storage (a mounted disk on a container host). Holds the SQLite file and MEDIA_ROOT.
DATA_DIR = Path(env("DATA_DIR")) if env("DATA_DIR") else None
if DATA_DIR:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        pass  # a mounted disk normally exists already; if it is unwritable, migrate fails with a clear error

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{(DATA_DIR or BASE_DIR) / 'db.sqlite3'}", conn_max_age=60
    )
}

REDIS_URL = env("REDIS_URL")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "wonderkidz",
        }
    }

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = []
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/me/"
LOGOUT_REDIRECT_URL = "/"

LANGUAGE_CODE = "fa"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = (DATA_DIR / "media") if DATA_DIR else (BASE_DIR / "media")
mimetypes.add_type("image/webp", ".webp")  # python:3.12-slim lacks it; matters when Django serves media itself
# Serve MEDIA_ROOT from Django itself. On by default in DEBUG; set SERVE_MEDIA=true on a demo host that has no
# object storage or front web server. Not for real production traffic.
SERVE_MEDIA = env("SERVE_MEDIA", DEBUG, bool)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "whitenoise.storage.CompressedStaticFilesStorage"
    },
}

# Object storage (Arvan / any S3-compatible). Activated only when a bucket is configured.
if env("S3_BUCKET"):
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": env("S3_BUCKET"),
            "endpoint_url": env("S3_ENDPOINT"),
            "access_key": env("S3_ACCESS_KEY"),
            "secret_key": env("S3_SECRET_KEY"),
            "region_name": env("S3_REGION", "ir-thr-at1"),
            "default_acl": "public-read",
            "querystring_auth": False,
            "file_overwrite": False,
        },
    }
    if env("S3_PUBLIC_URL"):
        MEDIA_URL = env("S3_PUBLIC_URL").rstrip("/") + "/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

SESSION_COOKIE_AGE = 60 * 60 * 24 * 90  # 90 days — phone is the identity, keep people logged in.

# ---- Product configuration ------------------------------------------------
LISTING_TTL_DAYS = env("LISTING_TTL_DAYS", 30, int)
NEW_ACCOUNT_LISTING_CAP = env("NEW_ACCOUNT_LISTING_CAP", 5, int)
LISTING_MAX_IMAGES = 8
LISTING_MIN_IMAGES = 1
MODERATION_MODEL = env("MODERATION_MODEL", "ai_first")  # pre_approval | post_review | ai_first
MODERATION_SLA_HOURS = 2
IMAGE_SIZES = {"thumb": (480, 360), "gallery": (1200, 900)}

# OTP / SMS — plug-and-play backend. console prints codes to stdout.
SMS_BACKEND = env("SMS_BACKEND", "console")  # console | kavenegar | smsir
KAVENEGAR_API_KEY = env("KAVENEGAR_API_KEY", "")
KAVENEGAR_OTP_TEMPLATE = env("KAVENEGAR_OTP_TEMPLATE", "wonderkidz-otp")
SMSIR_API_KEY = env("SMSIR_API_KEY", "")
SMSIR_OTP_TEMPLATE_ID = env("SMSIR_OTP_TEMPLATE_ID", 0, int)
OTP_TTL_SECONDS = 120
OTP_LENGTH = 5
OTP_RATE_LIMIT_PER_HOUR = 5
OTP_DEV_CODE = env("OTP_DEV_CODE", "")  # if set (dev only), this code always verifies

# Payments — plug-and-play gateway. fake gateway auto-succeeds on a local page.
PAYMENT_GATEWAY = env("PAYMENT_GATEWAY", "fake")  # fake | zarinpal | idpay
ZARINPAL_MERCHANT_ID = env("ZARINPAL_MERCHANT_ID", "")
ZARINPAL_SANDBOX = env("ZARINPAL_SANDBOX", True, bool)
IDPAY_API_KEY = env("IDPAY_API_KEY", "")
IDPAY_SANDBOX = env("IDPAY_SANDBOX", True, bool)

CONTACT_PHONE = "09128890878"
CONTACT_EMAIL = "info@wonderkidz.net"

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}
