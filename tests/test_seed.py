from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Category, City, District
from apps.chat.models import Conversation
from apps.listings.models import Listing, ListingImage, Report
from apps.payments.models import Plan

from .utils import make_listing, media_settings


@media_settings
class SeedDemoTests(TestCase):
    def test_seed_runs_and_is_idempotent(self):
        out = StringIO()
        call_command("seed_demo", stdout=out)
        self.assertIn("Seed complete", out.getvalue())
        self.assertTrue(City.objects.filter(slug="tehran", is_active=True).exists())
        self.assertEqual(District.objects.filter(city__slug="tehran").count(), 3)
        self.assertEqual(Category.objects.filter(parent__isnull=True).count(), 10)
        self.assertTrue(Category.objects.filter(slug="lego-blocks", parent__slug="building").exists())
        self.assertGreaterEqual(Listing.objects.filter(status=Listing.Status.LIVE).count(), 20)
        self.assertGreaterEqual(Listing.objects.filter(status=Listing.Status.PENDING).count(), 2)
        self.assertTrue(Listing.objects.filter(status=Listing.Status.PENDING).exclude(auto_flags=[]).exists())
        self.assertTrue(Listing.objects.filter(status=Listing.Status.REJECTED).exclude(reject_reason="").exists())
        self.assertTrue(Listing.objects.filter(status=Listing.Status.SOLD).exists())
        for listing in Listing.objects.all():
            self.assertGreaterEqual(listing.images.count(), 1, listing.title)
        img = ListingImage.objects.first()
        self.assertTrue(img.image.name.endswith(".webp"))
        self.assertTrue(img.thumb.name.endswith(".webp"))
        self.assertGreater(img.width, 0)
        self.assertTrue(User.objects.filter(phone="09120000000", is_staff=True).exists())
        self.assertTrue(User.objects.filter(phone="09128890878", account_type=User.AccountType.OFFICIAL).exists())
        self.assertGreaterEqual(Conversation.objects.count(), 3)
        self.assertGreaterEqual(Report.objects.count(), 3)
        self.assertEqual(Plan.objects.filter(is_active=True).count(), 0)

        counts = (
            Listing.objects.count(), ListingImage.objects.count(), User.objects.count(),
            Conversation.objects.count(), Report.objects.count(), Category.objects.count(),
        )
        call_command("seed_demo", stdout=StringIO())
        self.assertEqual(
            counts,
            (
                Listing.objects.count(), ListingImage.objects.count(), User.objects.count(),
                Conversation.objects.count(), Report.objects.count(), Category.objects.count(),
            ),
        )


@media_settings
class ExpireCommandTests(TestCase):
    def test_expire_listings_command(self):
        old = make_listing()
        old.expires_at = timezone.now() - timezone.timedelta(days=1)
        old.save()
        fresh = make_listing()
        out = StringIO()
        call_command("expire_listings", stdout=out)
        self.assertIn("expired 1", out.getvalue())
        old.refresh_from_db()
        fresh.refresh_from_db()
        self.assertEqual(old.status, Listing.Status.EXPIRED)
        self.assertEqual(fresh.status, Listing.Status.LIVE)
