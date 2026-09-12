"""Nightly sweep: LIVE listings past expires_at become EXPIRED (and promoted flags lapse)."""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Expire live listings whose expires_at has passed."

    def handle(self, *args, **options):
        try:
            from apps.listings.services import expire_listings  # written by the listings agent
        except (ImportError, AttributeError):
            expire_listings = None

        if expire_listings is not None:
            n = expire_listings()
        else:
            from apps.listings.models import Listing

            now = timezone.now()
            n = Listing.objects.filter(status=Listing.Status.LIVE, expires_at__lt=now).update(
                status=Listing.Status.EXPIRED
            )
            Listing.objects.filter(is_promoted=True, promoted_until__lt=now).update(is_promoted=False)
        self.stdout.write(self.style.SUCCESS(f"expired {n or 0} listing(s)"))
