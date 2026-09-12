from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.chat.models import Conversation
from apps.listings.models import Listing, Report
from apps.moderation.models import ModerationDecision

from .utils import add_image, make_category, make_district, make_listing, make_staff, make_user, media_settings


@media_settings
class PanelAccessTests(TestCase):
    def test_anonymous_redirected_to_login(self):
        r = self.client.get(reverse("panel:queue"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/?next=/panel/", r["Location"])

    def test_non_staff_redirected_home(self):
        self.client.force_login(make_user())
        r = self.client.get(reverse("panel:queue"))
        self.assertRedirects(r, reverse("listings:home"))
        self.assertEqual(self.client.post(reverse("panel:approve", args=[1])).status_code, 302)


@media_settings
class QueueTests(TestCase):
    def setUp(self):
        cache.clear()
        self.op = make_staff()
        self.client.force_login(self.op)
        self.seller = make_user(name="علی م.")
        self.district = make_district()
        self.cat = make_category()
        self.pending = make_listing(owner=self.seller, status=Listing.Status.DRAFT, title="ماشین شارژی برقی کودک", category=self.cat, district=self.district)
        add_image(self.pending)
        self.pending.auto_flags = [{"code": "price_outlier", "level": "warn", "text": "قیمت بسیار پایین‌تر از میانگین دسته"}]
        self.pending.submit()

    def test_queue_lists_pending_with_flags(self):
        make_listing(owner=self.seller, category=self.cat, district=self.district, title="پازل چوبی حروف الفبا")
        r = self.client.get(reverse("panel:queue"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "ماشین شارژی برقی کودک")
        self.assertContains(r, "قیمت بسیار پایین‌تر")
        self.assertContains(r, "علی م.")
        self.assertNotContains(r, "پازل چوبی حروف الفبا")
        self.assertEqual(r.context["stats"]["pending_count"], 1)
        self.assertEqual(r.context["stats"]["live_count"], 1)
        checklist = dict((label, icon) for icon, label in r.context["items"][0]["checklist"])
        self.assertEqual(checklist["قیمت منطقی است"], "❌")

    def test_approve(self):
        r = self.client.post(reverse("panel:approve", args=[self.pending.pk]), HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "تأیید شد")
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Listing.Status.LIVE)
        self.assertEqual(self.pending.reviewed_by, self.op)
        self.assertIsNotNone(self.pending.published_at)
        self.assertGreater(self.pending.expires_at, timezone.now() + timezone.timedelta(days=29))
        d = ModerationDecision.objects.get()
        self.assertEqual(d.decision, ModerationDecision.Decision.APPROVE)
        self.assertEqual(d.operator, self.op)
        self.assertEqual(d.target_user, self.seller)
        self.assertEqual(d.listing_title, "ماشین شارژی برقی کودک")
        # second approve is a no-op
        r = self.client.post(reverse("panel:approve", args=[self.pending.pk]), HTTP_HX_REQUEST="true")
        self.assertContains(r, "قبلاً بررسی شده")
        self.assertEqual(ModerationDecision.objects.count(), 1)

    def test_approve_non_htmx_redirects(self):
        r = self.client.post(reverse("panel:approve", args=[self.pending.pk]))
        self.assertRedirects(r, reverse("panel:queue"))

    def test_reject(self):
        r = self.client.post(
            reverse("panel:reject", args=[self.pending.pk]),
            {"reason": "در عکس‌ها چهرهٔ کودک دیده می‌شود", "note": "عکس دوم را عوض کنید"},
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(r, "رد شد")
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Listing.Status.REJECTED)
        self.assertEqual(self.pending.reject_reason, "در عکس‌ها چهرهٔ کودک دیده می‌شود")
        self.assertEqual(self.pending.reject_note, "عکس دوم را عوض کنید")
        self.assertEqual(ModerationDecision.objects.get().decision, ModerationDecision.Decision.REJECT)
        # seller sees the reason on their profile
        self.client.force_login(self.seller)
        r = self.client.get(reverse("accounts:profile"))
        self.assertContains(r, "چهرهٔ کودک")

    def test_other_pages_render(self):
        for name in ("panel:reports", "panel:users", "panel:listings", "panel:stats", "panel:decisions"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertEqual(self.client.get(reverse("panel:user_detail", args=[self.seller.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("panel:listings") + "?status=pending&q=ماشین").status_code, 200)
        self.assertEqual(self.client.get(reverse("panel:users") + "?q=علی&f=banned").status_code, 200)


@media_settings
class ReportsAndUsersTests(TestCase):
    def setUp(self):
        cache.clear()
        self.op = make_staff()
        self.client.force_login(self.op)
        self.seller = make_user(name="فروشنده")
        self.reporter = make_user(name="گزارش‌دهنده")
        self.listing = make_listing(owner=self.seller, title="تاب و سرسرهٔ پلاستیکی")
        self.report = Report.objects.create(reporter=self.reporter, listing=self.listing, reason=Report.Reason.SCAM, priority=Report.Priority.URGENT)

    def test_reports_page(self):
        r = self.client.get(reverse("panel:reports"))
        self.assertContains(r, "تاب و سرسرهٔ پلاستیکی")
        self.assertContains(r, "فوری")
        self.assertEqual(r.context["stats"]["urgent_reports"], 1)

    def test_takedown_ban(self):
        other_live = make_listing(owner=self.seller)
        r = self.client.post(reverse("panel:resolve_report", args=[self.report.pk]), {"action": "takedown_ban"}, HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 200)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.RESOLVED)
        self.assertEqual(self.report.handled_by, self.op)
        self.listing.refresh_from_db()
        other_live.refresh_from_db()
        self.assertEqual(self.listing.status, Listing.Status.REMOVED)
        self.assertEqual(other_live.status, Listing.Status.REMOVED)
        self.seller.refresh_from_db()
        self.assertTrue(self.seller.is_banned)
        decisions = set(ModerationDecision.objects.values_list("decision", flat=True))
        self.assertEqual(decisions, {"takedown", "ban"})
        # already handled
        r = self.client.post(reverse("panel:resolve_report", args=[self.report.pk]), {"action": "dismiss"}, HTTP_HX_REQUEST="true")
        self.assertContains(r, "قبلاً رسیدگی شده")

    def test_dismiss(self):
        r = self.client.post(reverse("panel:resolve_report", args=[self.report.pk]), {"action": "dismiss"})
        self.assertRedirects(r, reverse("panel:reports"))
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.DISMISSED)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, Listing.Status.LIVE)
        self.assertEqual(ModerationDecision.objects.get().decision, ModerationDecision.Decision.DISMISS)

    def test_warn(self):
        self.client.post(reverse("panel:resolve_report", args=[self.report.pk]), {"action": "warn"})
        self.seller.refresh_from_db()
        self.assertEqual(self.seller.warnings_count, 1)
        self.report.refresh_from_db()
        self.assertEqual(self.report.resolution, "تذکر به فروشنده")

    def test_chat_report_warns_other_party(self):
        conv = Conversation.objects.create(listing=self.listing, buyer=self.reporter, seller=self.seller)
        rep = Report.objects.create(reporter=self.reporter, conversation=conv, reason=Report.Reason.ABUSE)
        self.client.post(reverse("panel:resolve_report", args=[rep.pk]), {"action": "warn"})
        self.seller.refresh_from_db()
        self.assertEqual(self.seller.warnings_count, 1)
        rep.refresh_from_db()
        self.assertEqual(rep.resolution, "اخطار به کاربر")

    def test_ban_user_toggle_removes_live_listings(self):
        pending = make_listing(owner=self.seller, status=Listing.Status.PENDING)
        r = self.client.post(reverse("panel:ban_user", args=[self.seller.pk]), {"reason": "اسپم"})
        self.assertRedirects(r, reverse("panel:user_detail", args=[self.seller.pk]))
        self.seller.refresh_from_db()
        self.assertTrue(self.seller.is_banned)
        self.assertEqual(self.seller.ban_reason, "اسپم")
        for lst in (self.listing, pending):
            lst.refresh_from_db()
            self.assertEqual(lst.status, Listing.Status.REMOVED)
        self.client.post(reverse("panel:ban_user", args=[self.seller.pk]))
        self.seller.refresh_from_db()
        self.assertFalse(self.seller.is_banned)
        # cannot ban self / superuser
        self.client.post(reverse("panel:ban_user", args=[self.op.pk]))
        self.op.refresh_from_db()
        self.assertFalse(self.op.is_banned)

    def test_takedown_listing(self):
        r = self.client.post(reverse("panel:takedown", args=[self.listing.pk]), {"reason": "کالای ممنوعه"}, HTTP_HX_REQUEST="true")
        self.assertContains(r, "حذف شد")
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, Listing.Status.REMOVED)
        self.assertEqual(ModerationDecision.objects.get().reason, "کالای ممنوعه")

    def test_decisions_page_shows_today(self):
        self.client.post(reverse("panel:resolve_report", args=[self.report.pk]), {"action": "dismiss"})
        r = self.client.get(reverse("panel:decisions"))
        self.assertEqual(r.context["total_today"], 1)
        self.assertContains(r, "تاب و سرسرهٔ پلاستیکی")

    def test_django_admin_available(self):
        for url in ("/admin/", "/admin/listings/listing/", "/admin/accounts/user/", "/admin/moderation/moderationdecision/", "/admin/payments/plan/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
