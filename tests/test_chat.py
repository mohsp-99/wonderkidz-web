from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.chat.models import Conversation, Message
from apps.listings.models import Listing

from .utils import make_listing, make_user, media_settings


@media_settings
class ChatTests(TestCase):
    def setUp(self):
        cache.clear()
        self.seller = make_user(name="مریم ر.")
        self.buyer = make_user(name="سارا م.")
        self.listing = make_listing(owner=self.seller, title="لگو کلاسیک ۵۰۰ قطعه")

    def _start(self, user=None):
        self.client.force_login(user or self.buyer)
        return self.client.get(reverse("chat:start", args=[self.listing.code]))

    def test_inbox_requires_login(self):
        r = self.client.get(reverse("chat:inbox"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r["Location"])

    def test_start_creates_conversation_with_system_message(self):
        r = self._start()
        conv = Conversation.objects.get(listing=self.listing, buyer=self.buyer)
        self.assertEqual(conv.seller, self.seller)
        self.assertRedirects(r, reverse("chat:thread", args=[conv.pk]))
        sys_msg = conv.messages.get()
        self.assertTrue(sys_msg.is_system)
        self.assertIsNone(sys_msg.sender)
        self.assertIn("بیعانه", sys_msg.body)
        # idempotent
        self._start()
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(Message.objects.count(), 1)

    def test_owner_cannot_chat_with_self(self):
        r = self._start(self.seller)
        self.assertRedirects(r, self.listing.get_absolute_url())
        self.assertFalse(Conversation.objects.exists())

    def test_start_refused_when_chat_disabled_or_not_live(self):
        self.listing.allow_chat = False
        self.listing.save()
        self._start()
        self.assertFalse(Conversation.objects.exists())
        self.listing.allow_chat = True
        self.listing.status = Listing.Status.SOLD
        self.listing.save()
        self._start()
        self.assertFalse(Conversation.objects.exists())

    def test_banned_user_cannot_start(self):
        self.buyer.is_banned = True
        self.buyer.save()
        self._start()
        self.assertFalse(Conversation.objects.exists())

    def test_non_participant_forbidden(self):
        self._start()
        conv = Conversation.objects.get()
        stranger = make_user()
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(reverse("chat:thread", args=[conv.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("chat:messages", args=[conv.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("chat:send", args=[conv.pk]), {"body": "hi"}).status_code, 403)
        self.assertEqual(self.client.post(reverse("chat:feedback", args=[conv.pk]), {"value": "good"}).status_code, 403)

    def test_send_appends_message_and_updates_timestamp(self):
        self._start()
        conv = Conversation.objects.get()
        before = conv.last_message_at
        r = self.client.post(reverse("chat:send", args=[conv.pk]), {"body": "  سلام، لگو هنوز هست؟  "})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "سلام، لگو هنوز هست؟")
        msg = conv.messages.filter(sender=self.buyer).get()
        self.assertEqual(msg.body, "سلام، لگو هنوز هست؟")
        conv.refresh_from_db()
        self.assertGreater(conv.last_message_at, before)
        # empty body ignored
        self.client.post(reverse("chat:send", args=[conv.pk]), {"body": "   "})
        self.assertEqual(conv.messages.count(), 2)

    def test_thread_and_unread_flow(self):
        self._start()
        conv = Conversation.objects.get()
        self.client.post(reverse("chat:send", args=[conv.pk]), {"body": "سلام"})
        self.assertEqual(conv.unread_for(self.seller), 1)
        self.assertEqual(conv.unread_for(self.buyer), 0)

        # seller sees the badge in the header context, then reads the thread
        self.client.force_login(self.seller)
        r = self.client.get(reverse("listings:home"))
        self.assertEqual(r.context["unread_chat_count"], 1)
        r = self.client.get(reverse("chat:thread", args=[conv.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "سارا م.")
        self.assertContains(r, "لگو کلاسیک ۵۰۰ قطعه")
        self.assertEqual(conv.unread_for(self.seller), 0)

        # seller replies; buyer polls the fragment which marks it read
        self.client.post(reverse("chat:send", args=[conv.pk]), {"body": "بله هست"})
        self.assertEqual(conv.unread_for(self.buyer), 1)
        self.client.force_login(self.buyer)
        r = self.client.get(reverse("chat:messages", args=[conv.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "بله هست")
        self.assertNotContains(r, "<html")
        self.assertEqual(conv.unread_for(self.buyer), 0)

    def test_inbox_lists_conversations(self):
        self._start()
        conv = Conversation.objects.get()
        self.client.post(reverse("chat:send", args=[conv.pk]), {"body": "پس فردا ساعت ۵ میدان کاج خوبه؟"})
        r = self.client.get(reverse("chat:inbox"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "شما: پس فردا")
        self.assertContains(r, "مریم ر.")

    def test_sold_listing_hides_compose_and_accepts_feedback(self):
        self._start()
        conv = Conversation.objects.get()
        self.listing.mark_sold()
        r = self.client.get(reverse("chat:thread", args=[conv.pk]))
        self.assertContains(r, "معامله انجام شد؟")
        self.assertNotContains(r, "ct-compose")
        self.assertEqual(self.client.post(reverse("chat:send", args=[conv.pk]), {"body": "x"}).status_code, 409)
        r = self.client.post(reverse("chat:feedback", args=[conv.pk]), {"value": "good"})
        self.assertRedirects(r, reverse("chat:thread", args=[conv.pk]))
        conv.refresh_from_db()
        self.assertEqual(conv.buyer_feedback, "good")
        self.assertEqual(conv.seller_feedback, "")
        self.assertEqual(self.client.post(reverse("chat:feedback", args=[conv.pk]), {"value": "meh"}).status_code, 400)

    def test_anonymous_unread_count_is_zero(self):
        r = self.client.get(reverse("listings:home"))
        self.assertEqual(r.context["unread_chat_count"], 0)
