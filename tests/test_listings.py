from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.listings import services
from apps.listings.models import Listing, ListingImage, PhoneReveal, Report, SavedListing

from .utils import (
    add_image,
    listing_post_data,
    make_brand,
    make_category,
    make_city,
    make_district,
    make_listing,
    make_user,
    media_settings,
    upload_file,
)


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.city = make_city()
        self.district = make_district(self.city)
        self.district2 = make_district(self.city, "پونک", "punak")
        self.root = make_category()
        self.sub = make_category("لگو و بلوک", "lego-blocks", parent=self.root)
        self.other_root = make_category("عروسک و فیگور", "dolls")
        self.brand = make_brand()
        self.user = make_user(name="مریم ر.", city=self.city, district=self.district)


@media_settings
class PostWizardTests(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.url = reverse("listings:post")

    def test_get_renders_stepper(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "ثبت آگهی")
        self.assertContains(r, "عکس کودکان ممنوع است")

    def test_requires_login(self):
        self.client.logout()
        r = self.client.get(self.url)
        self.assertRedirects(r, f"{reverse('accounts:login')}?next={self.url}")

    def test_post_creates_listing_with_images(self):
        data = listing_post_data(self.sub, self.district, brand=self.brand.pk)
        data["images"] = [upload_file("a.jpg"), upload_file("b.jpg", (30, 120, 200))]
        r = self.client.post(self.url, data)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith(reverse("accounts:profile")))
        listing = Listing.objects.get()
        self.assertEqual(listing.owner, self.user)
        self.assertEqual(listing.type, Listing.Type.SELL)
        self.assertEqual(listing.price, 1_250_000)
        self.assertEqual(listing.original_price, 3_400_000)
        self.assertEqual(listing.brand, self.brand)
        self.assertTrue(listing.has_box and listing.is_complete and listing.attested_safe)
        self.assertEqual(listing.images.count(), 2)
        for img in listing.images.all():
            self.assertTrue(img.image.name.endswith(".webp"))
            self.assertTrue(img.thumb.name.endswith(".webp"))
            self.assertEqual((img.width, img.height), (640, 480))
        self.assertTrue(listing.search_text)
        self.assertIn("lego", listing.search_text)
        self.assertEqual(listing.percent_off, 63)
        # ai_first + clean (user joined 30 days ago) → published immediately
        self.assertEqual(listing.status, Listing.Status.LIVE)
        self.assertIsNotNone(listing.expires_at)

    def test_new_account_goes_to_review(self):
        newbie = make_user(joined_days_ago=0)
        self.client.force_login(newbie)
        data = listing_post_data(self.sub, self.district)
        data["images"] = [upload_file()]
        self.client.post(self.url, data)
        listing = Listing.objects.get()
        self.assertEqual(listing.status, Listing.Status.PENDING)
        self.assertIn("new_account", [f["code"] for f in listing.auto_flags])

    @override_settings(MODERATION_MODEL="pre_approval")
    def test_pre_approval_always_pending(self):
        data = listing_post_data(self.sub, self.district)
        data["images"] = [upload_file(), upload_file("b.jpg")]
        self.client.post(self.url, data)
        listing = Listing.objects.get()
        self.assertEqual(listing.status, Listing.Status.PENDING)
        self.assertIsNotNone(listing.submitted_at)

    @override_settings(MODERATION_MODEL="post_review")
    def test_post_review_publishes_even_when_flagged(self):
        newbie = make_user(joined_days_ago=0)
        self.client.force_login(newbie)
        data = listing_post_data(self.sub, self.district)
        data["images"] = [upload_file()]
        self.client.post(self.url, data)
        listing = Listing.objects.get()
        self.assertEqual(listing.status, Listing.Status.LIVE)
        self.assertTrue(listing.auto_flags)

    def test_description_with_phone_rejected(self):
        data = listing_post_data(self.sub, self.district, description="تماس بگیرید 09123456789 هر روز عصر خونه هستم")
        data["images"] = [upload_file()]
        r = self.client.post(self.url, data)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "شمارهٔ تماس، لینک شبکه‌های اجتماعی")
        self.assertFalse(Listing.objects.exists())

    def test_attestation_required(self):
        data = listing_post_data(self.sub, self.district)
        data.pop("attested_safe")
        data["images"] = [upload_file()]
        r = self.client.post(self.url, data)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "نبود عکس کودک را تأیید کنید")
        self.assertFalse(Listing.objects.exists())

    def test_image_required(self):
        r = self.client.post(self.url, listing_post_data(self.sub, self.district))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "حداقل یک عکس لازم است")
        self.assertFalse(Listing.objects.exists())

    def test_too_many_images(self):
        data = listing_post_data(self.sub, self.district)
        data["images"] = [upload_file(f"{i}.jpg") for i in range(9)]
        r = self.client.post(self.url, data)
        self.assertContains(r, "حداکثر ۸ عکس")
        self.assertFalse(Listing.objects.exists())

    def test_invalid_image_file(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        data = listing_post_data(self.sub, self.district)
        data["images"] = [SimpleUploadedFile("x.jpg", b"not an image", content_type="image/jpeg")]
        r = self.client.post(self.url, data)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "فایل عکس معتبر نیست")
        self.assertFalse(Listing.objects.exists())

    def test_cap_enforced(self):
        self.user.listing_cap = 1
        self.user.save()
        make_listing(owner=self.user, district=self.district, category=self.sub)
        r = self.client.get(self.url, follow=True)
        self.assertRedirects(r, reverse("accounts:profile"))
        self.assertContains(r, "سقف آگهی فعال")
        data = listing_post_data(self.sub, self.district)
        data["images"] = [upload_file()]
        self.client.post(self.url, data)
        self.assertEqual(Listing.objects.count(), 1)

    def test_banned_user_blocked(self):
        self.user.is_banned = True
        self.user.save()
        r = self.client.get(self.url, follow=True)
        self.assertContains(r, "مسدود شده")

    def test_disabled_type_rejected(self):
        data = listing_post_data(self.sub, self.district, type="free")
        data["images"] = [upload_file()]
        r = self.client.post(self.url, data)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Listing.objects.exists())
        self.assertEqual(r.context["form"].errors["type"], ["این نوع آگهی هنوز فعال نشده است."])
        # the wizard only lists the offending field label in its summary (the type step renders via Alpine)
        self.assertContains(r, "<b>نوع آگهی</b>")

    def test_no_contact_channel_rejected(self):
        data = listing_post_data(self.sub, self.district)
        data.pop("allow_chat")
        data.pop("allow_phone")
        data["images"] = [upload_file()]
        r = self.client.post(self.url, data)
        self.assertContains(r, "حداقل یکی از راه‌های تماس")


@media_settings
class AutoChecksTests(Base):
    def test_flags(self):
        listing = make_listing(owner=self.user, category=self.sub, district=self.district, price=1_000_000)
        self.assertEqual([f["code"] for f in services.run_auto_checks(listing)], ["single_image"])

        listing.title = "لگو تماس 09123456789"
        listing.hygiene_note = "کوتاه"
        codes = [f["code"] for f in services.run_auto_checks(listing)]
        self.assertIn("contact_in_text", codes)
        self.assertIn("hygiene_missing", codes)

        listing.title = "صندلی خودرو کودک"
        flags = services.run_auto_checks(listing)
        blocked = [f for f in flags if f["code"] == "banned_item"]
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0]["level"], "block")

    def test_price_outlier_against_median(self):
        for p in (1_000_000, 1_200_000, 1_400_000):
            lst = make_listing(owner=self.user, category=self.sub, district=self.district, price=p)
            add_image(lst)
        self.assertEqual(services.median_price(self.sub), 1_200_000)
        self.assertEqual(services.median_price(self.root), 1_200_000)
        cheap = make_listing(owner=self.user, category=self.sub, district=self.district, price=200_000, status=Listing.Status.DRAFT)
        add_image(cheap)
        add_image(cheap, 1)
        codes = [f["code"] for f in services.run_auto_checks(cheap)]
        self.assertIn("price_outlier", codes)
        self.assertNotIn("single_image", codes)

    def test_banned_keyword_blocks_even_in_post_review(self):
        with override_settings(MODERATION_MODEL="post_review"):
            lst = make_listing(owner=self.user, category=self.sub, district=self.district, status=Listing.Status.DRAFT, title="لباس بچگانه سایز ۳")
            services.submit_listing(lst)
        self.assertEqual(lst.status, Listing.Status.PENDING)

    def test_expire_listings_service(self):
        old = make_listing(owner=self.user, category=self.sub, district=self.district)
        old.expires_at = timezone.now() - timezone.timedelta(minutes=1)
        old.save()
        keep = make_listing(owner=self.user, category=self.sub, district=self.district)
        self.assertEqual(services.expire_listings(), 1)
        old.refresh_from_db()
        keep.refresh_from_db()
        self.assertEqual(old.status, Listing.Status.EXPIRED)
        self.assertEqual(keep.status, Listing.Status.LIVE)
        old.renew()
        self.assertEqual(old.status, Listing.Status.LIVE)
        self.assertGreater(old.expires_at, timezone.now())


@media_settings
class SearchTests(Base):
    def setUp(self):
        super().setUp()
        self.brand2 = make_brand("BRIO", "brio")
        self.a = make_listing(owner=self.user, category=self.sub, district=self.district, title="لگو کلاسیک ۵۰۰ قطعه", price=1_250_000, age_range="5-8", condition="likenew", brand=self.brand)
        self.b = make_listing(owner=self.user, category=self.sub, district=self.district2, title="مگنت ساختنی پیکاسوتایلز", price=1_650_000, age_range="3-5", condition="new", brand=self.brand2, has_box=True)
        self.c = make_listing(owner=self.user, category=self.other_root, district=self.district, title="عروسک خرس تدي پارچه‌ای", price=95_000, age_range="1-3", condition="used")
        self.pending = make_listing(owner=self.user, category=self.sub, district=self.district, title="پنهان", status=Listing.Status.PENDING)
        add_image(self.a)
        self.url = reverse("listings:search")

    def titles(self, r):
        return [lst.title for lst in r.context["page"].object_list]

    def test_only_live_in_current_city(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(self.titles(r)), {self.a.title, self.b.title, self.c.title})
        self.assertEqual(r.context["total"], 3)

    def test_q_normalizes_arabic_yeh(self):
        r = self.client.get(self.url, {"q": "تدی"})  # search text stored with ي normalized to ی
        self.assertEqual(self.titles(r), [self.c.title])
        r = self.client.get(self.url, {"q": "LEGO"})
        self.assertEqual(self.titles(r), [self.a.title])
        r = self.client.get(self.url, {"q": "لگو ۵۰۰"})
        self.assertEqual(self.titles(r), [self.a.title])

    def test_filters(self):
        self.assertEqual(self.titles(self.client.get(self.url, {"age": "3-5"})), [self.b.title])
        self.assertEqual(set(self.titles(self.client.get(self.url, {"age": ["3-5", "5-8"]}))), {self.a.title, self.b.title})
        self.assertEqual(self.titles(self.client.get(self.url, {"cond": "used"})), [self.c.title])
        self.assertEqual(self.titles(self.client.get(self.url, {"min": "۱۰۰٬۰۰۰", "max": "1300000"})), [self.a.title])
        self.assertEqual(self.titles(self.client.get(self.url, {"brand": "brio"})), [self.b.title])
        self.assertEqual(set(self.titles(self.client.get(self.url, {"dist": "saadat-abad"}))), {self.a.title, self.c.title})
        self.assertEqual(self.titles(self.client.get(self.url, {"box": "1"})), [self.b.title])
        self.assertEqual(self.titles(self.client.get(self.url, {"photo": "1"})), [self.a.title])
        self.assertEqual(self.titles(self.client.get(self.url, {"cat": "building", "cond": "new"})), [self.b.title])

    def test_sort(self):
        self.assertEqual(self.titles(self.client.get(self.url, {"sort": "cheapest"})), [self.c.title, self.a.title, self.b.title])
        self.assertEqual(self.titles(self.client.get(self.url, {"sort": "expensive"})), [self.b.title, self.a.title, self.c.title])
        self.client.force_login(make_user(district=self.district2, city=self.city))
        self.assertEqual(self.titles(self.client.get(self.url, {"sort": "nearest"}))[0], self.b.title)

    def test_category_routes(self):
        r = self.client.get(reverse("listings:category", args=["building"]))
        self.assertEqual(set(self.titles(r)), {self.a.title, self.b.title})
        self.assertContains(r, "<title>لگو و ساختنی، تهران | وندرکیدز")
        r = self.client.get(reverse("listings:category", args=["lego-blocks"]))
        self.assertEqual(r.context["selected_root"], self.root)
        r = self.client.get(reverse("listings:category_district", args=["building", "punak"]))
        self.assertEqual(self.titles(r), [self.b.title])
        self.assertContains(r, "پونک | وندرکیدز")
        self.assertEqual(self.client.get(reverse("listings:category", args=["nope"])).status_code, 404)

    def test_applied_pills_and_facets(self):
        r = self.client.get(self.url, {"age": "5-8", "cond": "likenew", "dist": "saadat-abad", "max": "2000000"})
        labels = [p[2] for p in r.context["pills"]]
        self.assertIn("۵ تا ۸ سال", labels)
        self.assertIn("در حد نو", labels)
        self.assertIn("سعادت‌آباد", labels)
        self.assertIn("تا ۲٬۰۰۰٬۰۰۰ تومان", labels)
        self.assertEqual(r.context["cond_counts"]["used"], 1)
        self.assertEqual(r.context["dist_counts"]["punak"], 1)

    def test_htmx_page_returns_fragment(self):
        for i in range(25):
            make_listing(owner=self.user, category=self.sub, district=self.district, title=f"آگهی شماره {i}")
        r = self.client.get(self.url, {"page": 2}, HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "<html")
        self.assertNotContains(r, 'class="hd"')
        self.assertContains(r, 'class="card"')
        self.assertEqual(len(r.context["page"].object_list), 4)
        r = self.client.get(self.url, {"page": 2})
        self.assertContains(r, "<html")

    def test_header_search_form_targets_search(self):
        r = self.client.get(reverse("listings:home"))
        self.assertContains(r, f'action="{self.url}"')

    def test_save_search(self):
        from apps.accounts.models import SavedSearch

        r = self.client.post(reverse("listings:save_search"), {"querystring": "q=لگو&age=3-5", "label": "لگو"})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(SavedSearch.objects.exists())
        self.client.force_login(self.user)
        r = self.client.post(reverse("listings:save_search"), {"querystring": "q=لگو&age=3-5", "label": "لگو"})
        self.assertRedirects(r, f"{self.url}?q=لگو&age=3-5", fetch_redirect_response=False)
        self.assertEqual(SavedSearch.objects.get(user=self.user).label, "لگو")


@media_settings
class HomeAndPagesTests(Base):
    def test_home(self):
        lst = make_listing(owner=self.user, category=self.sub, district=self.district, title="لگو کلاسیک ۵۰۰ قطعه")
        make_listing(owner=self.user, category=self.sub, district=self.district, status=Listing.Status.SOLD)
        r = self.client.get(reverse("listings:home"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "لگو کلاسیک ۵۰۰ قطعه")
        self.assertContains(r, lst.get_absolute_url())
        self.assertEqual(r.context["live_count"], 1)
        self.assertEqual(r.context["sold_count"], 1)
        roots = {c.slug: c.live_count for c in r.context["roots"]}
        self.assertEqual(roots["building"], 1)
        self.assertEqual(roots["dolls"], 0)

    def test_static_pages(self):
        for slug in ("about", "posting-guide", "safety", "terms", "privacy", "faq"):
            self.assertEqual(self.client.get(reverse("listings:page", args=[slug])).status_code, 200, slug)
        self.assertEqual(self.client.get(reverse("listings:page", args=["nope"])).status_code, 404)

    def test_sitemap_and_robots(self):
        lst = make_listing(owner=self.user, category=self.sub, district=self.district)
        hidden = make_listing(owner=self.user, category=self.sub, district=self.district, status=Listing.Status.PENDING)
        r = self.client.get("/sitemap.xml")
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn(lst.get_absolute_url(), body)
        self.assertNotIn(hidden.get_absolute_url(), body)
        self.assertIn("/s/building/", body)
        r = self.client.get("/robots.txt")
        self.assertContains(r, "Disallow: /panel/")
        self.assertContains(r, "sitemap.xml")


@media_settings
class DetailTests(Base):
    def setUp(self):
        super().setUp()
        self.listing = make_listing(
            owner=self.user, category=self.sub, district=self.district, title="لگو کلاسیک ۵۰۰ قطعه با جعبهٔ اصلی",
            price=1_250_000, original_price=3_400_000, meetup_hint="میدان کاج، جلوی کتاب‌فروشی",
        )
        add_image(self.listing)
        self.url = self.listing.get_absolute_url()

    def test_detail_renders(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "لگو کلاسیک ۵۰۰ قطعه با جعبهٔ اصلی")
        self.assertContains(r, "۱٬۲۵۰٬۰۰۰")
        self.assertContains(r, "۶۳٪")
        self.assertContains(r, "میدان کاج")
        self.assertContains(r, '"@type": "Product"')
        self.assertContains(r, self.listing.images.first().image.url)

    def test_short_url_and_wrong_slug_redirect(self):
        r = self.client.get(reverse("listings:detail_short", args=[self.listing.code]))
        self.assertEqual(r.status_code, 200)
        r = self.client.get(f"/v/{self.listing.code}/wrong-slug/")
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r["Location"], self.url)

    def test_view_count_once_per_session(self):
        self.client.get(self.url)
        self.client.get(self.url)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.views_count, 1)
        from django.test import Client

        Client().get(self.url)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.views_count, 2)

    def test_non_live_hidden_from_strangers_visible_to_owner(self):
        self.listing.status = Listing.Status.PENDING
        self.listing.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.client.force_login(make_user(is_staff=True))
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.get("/v/000000/").status_code, 404)

    def test_related_excludes_self_and_other_roots(self):
        same = make_listing(owner=self.user, category=self.root, district=self.district)
        other = make_listing(owner=self.user, category=self.other_root, district=self.district)
        r = self.client.get(self.url)
        related = list(r.context["related"])
        self.assertIn(same, related)
        self.assertNotIn(other, related)
        self.assertNotIn(self.listing, related)

    def test_reveal_phone(self):
        url = reverse("listings:reveal", args=[self.listing.code])
        r = self.client.post(url, HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 200)
        self.assertIn("/login/?next=", r["HX-Redirect"])
        r = self.client.post(url)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r["Location"])

        buyer = make_user()
        self.client.force_login(buyer)
        r = self.client.post(url, HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "۰۹۱۲")
        self.assertContains(r, 'id="phonebox"')
        self.assertEqual(PhoneReveal.objects.filter(listing=self.listing, user=buyer).count(), 1)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.reveals_count, 1)
        self.client.post(url)  # second reveal by same user does not double count
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.reveals_count, 1)
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_reveal_denied_when_phone_hidden(self):
        self.listing.allow_phone = False
        self.listing.save()
        self.client.force_login(make_user())
        r = self.client.post(reverse("listings:reveal", args=[self.listing.code]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, self.user.phone)
        self.assertFalse(PhoneReveal.objects.exists())

    def test_reveal_rate_limited(self):
        buyer = make_user()
        self.client.force_login(buyer)
        cache.set(f"reveal:{buyer.pk}", 30, 3600)
        r = self.client.post(reverse("listings:reveal", args=[self.listing.code]))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(PhoneReveal.objects.exists())

    def test_toggle_save(self):
        url = reverse("listings:save", args=[self.listing.code])
        self.assertEqual(self.client.post(url).status_code, 302)
        buyer = make_user()
        self.client.force_login(buyer)
        r = self.client.post(url, HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(SavedListing.objects.filter(user=buyer, listing=self.listing).exists())
        r = self.client.post(url)
        self.assertRedirects(r, self.url)
        self.assertFalse(SavedListing.objects.filter(user=buyer).exists())
        SavedListing.objects.create(user=buyer, listing=self.listing)
        r = self.client.get(reverse("accounts:profile"))
        self.assertContains(r, self.listing.title)

    def test_report(self):
        url = reverse("listings:report", args=[self.listing.code])
        self.assertEqual(self.client.post(url, {"reason": "scam"}).status_code, 302)
        self.assertFalse(Report.objects.exists())
        reporter = make_user()
        self.client.force_login(reporter)
        r = self.client.post(url, {"reason": "scam", "note": "بیعانه خواست"})
        self.assertRedirects(r, self.url)
        rep = Report.objects.get()
        self.assertEqual(rep.reporter, reporter)
        self.assertEqual(rep.listing, self.listing)
        self.assertEqual(rep.priority, Report.Priority.URGENT)
        self.client.post(url, {"reason": "mismatch"})
        self.assertEqual(Report.objects.get(reason="mismatch").priority, Report.Priority.NORMAL)
        r = self.client.post(url, {"reason": ""}, follow=True)
        self.assertContains(r, "دلیل گزارش را انتخاب کنید")


@media_settings
class OwnerActionTests(Base):
    def setUp(self):
        super().setUp()
        self.listing = make_listing(owner=self.user, category=self.sub, district=self.district, price=1_250_000)
        add_image(self.listing)
        self.stranger = make_user()

    def _owner_only(self, name, expect_status):
        url = reverse(name, args=[self.listing.code])
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 405)
        r = self.client.post(url)
        self.assertEqual(r.status_code, 302)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, expect_status)

    def test_mark_sold(self):
        self._owner_only("listings:mark_sold", Listing.Status.SOLD)
        self.assertIsNotNone(self.listing.sold_at)

    def test_delete(self):
        self._owner_only("listings:delete", Listing.Status.REMOVED)
        self.assertEqual(self.client.get(self.listing.get_absolute_url()).status_code, 200)  # owner still sees it
        self.client.logout()
        self.assertEqual(self.client.get(self.listing.get_absolute_url()).status_code, 404)

    def test_renew(self):
        self.listing.expires_at = timezone.now() + timezone.timedelta(days=3)
        self.listing.save()
        self.assertTrue(self.listing.is_expiring_soon)
        self._owner_only("listings:renew", Listing.Status.LIVE)
        self.assertGreater(self.listing.expires_at, timezone.now() + timezone.timedelta(days=29))

    def test_edit_price_change_sends_back_to_review(self):
        self.client.force_login(self.user)
        url = reverse("listings:edit", args=[self.listing.code])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.listing.title)
        data = listing_post_data(self.sub, self.district, title=self.listing.title, description=self.listing.description, hygiene_note=self.listing.hygiene_note)
        data["price"] = "1250000"
        data["meetup_hint"] = "پارک"
        self.client.post(url, data)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, Listing.Status.LIVE)  # cosmetic change stays live
        self.assertEqual(self.listing.meetup_hint, "پارک")
        with override_settings(MODERATION_MODEL="pre_approval"):
            data["price"] = "999000"
            self.client.post(url, data)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, Listing.Status.PENDING)
        self.assertEqual(self.listing.price, 999_000)
        self.assertEqual(self.listing.images.count(), 1)

    def test_edit_rejected_resubmits(self):
        self.listing.reject("دسته‌بندی اشتباه است")
        self.client.force_login(self.user)
        data = listing_post_data(self.sub, self.district, title=self.listing.title, description=self.listing.description, hygiene_note=self.listing.hygiene_note)
        self.client.post(reverse("listings:edit", args=[self.listing.code]), data)
        self.listing.refresh_from_db()
        self.assertIn(self.listing.status, (Listing.Status.LIVE, Listing.Status.PENDING))
        self.assertEqual(self.listing.reject_reason, "")

    def test_edit_forbidden_for_stranger_and_sold(self):
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(reverse("listings:edit", args=[self.listing.code])).status_code, 404)
        self.listing.mark_sold()
        self.client.force_login(self.user)
        r = self.client.get(reverse("listings:edit", args=[self.listing.code]))
        self.assertRedirects(r, reverse("accounts:profile"))

    def test_upload_and_delete_image(self):
        self.client.force_login(self.user)
        r = self.client.post(reverse("listings:upload_image"), {"code": self.listing.code, "images": [upload_file("n.jpg")]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.listing.images.count(), 2)
        first, second = list(self.listing.images.all())
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.post(reverse("listings:delete_image", args=[second.pk])).status_code, 403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse("listings:delete_image", args=[second.pk])).status_code, 200)
        self.assertEqual(self.listing.images.count(), 1)
        self.assertEqual(self.client.post(reverse("listings:delete_image", args=[first.pk])).status_code, 400)
        self.assertTrue(ListingImage.objects.filter(pk=first.pk).exists())
