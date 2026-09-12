from django.conf import settings
from django.db import models
from django.urls import reverse


class Conversation(models.Model):
    listing = models.ForeignKey("listings.Listing", on_delete=models.CASCADE, related_name="conversations")
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="buying_conversations")
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="selling_conversations")
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_closed = models.BooleanField(default=False)
    buyer_feedback = models.CharField(max_length=10, blank=True)  # good | bad
    seller_feedback = models.CharField(max_length=10, blank=True)

    class Meta:
        unique_together = [("listing", "buyer")]
        ordering = ["-last_message_at"]
        verbose_name = "گفت‌وگو"
        verbose_name_plural = "گفت‌وگوها"

    def __str__(self):
        return f"#{self.pk} {self.listing.title}"

    def get_absolute_url(self):
        return reverse("chat:thread", args=[self.pk])

    def other(self, user):
        return self.seller if user == self.buyer else self.buyer

    def unread_for(self, user):
        return self.messages.filter(is_read=False).exclude(sender=user).exclude(sender__isnull=True).count()

    def last_message(self):
        return self.messages.order_by("-created_at").first()


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)  # null = system
    body = models.TextField(max_length=2000)
    is_system = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "پیام"
        verbose_name_plural = "پیام‌ها"
