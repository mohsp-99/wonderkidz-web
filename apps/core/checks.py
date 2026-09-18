"""System checks that catch deployment mistakes at `migrate`/`check` time instead of on the first request."""
from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.caches)
def redis_client_installed(app_configs, **kwargs):
    """REDIS_URL switches the cache to RedisCache, which imports `redis` lazily on the first cache call.
    Without the package every cache access (OTP rate limit, phone reveal counters) raises inside a view."""
    if not getattr(settings, "REDIS_URL", None):
        return []
    try:
        import redis  # noqa: F401
    except ImportError:
        return [
            Error(
                "REDIS_URL is set but the 'redis' Python package is not installed; every cache call would raise.",
                hint="Install requirements.txt (it includes redis) or unset REDIS_URL.",
                id="core.E001",
            )
        ]
    return []
