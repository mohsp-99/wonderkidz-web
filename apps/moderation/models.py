from django.conf import settings
from django.db import models


class ModerationDecision(models.Model):
    class Decision(models.TextChoices):
        APPROVE = "approve", "تأیید"
        REJECT = "reject", "رد"
        TAKEDOWN = "takedown", "حذف"
        WARN = "warn", "اخطار"
        BAN = "ban", "مسدودسازی"
        DISMISS = "dismiss", "بی‌اشکال"

    listing = models.ForeignKey("listings.Listing", null=True, blank=True, on_delete=models.SET_NULL, related_name="decisions")
    report = models.ForeignKey("listings.Report", null=True, blank=True, on_delete=models.SET_NULL, related_name="decisions")
    target_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="received_decisions")
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="decisions")
    decision = models.CharField(max_length=10, choices=Decision.choices)
    reason = models.CharField(max_length=200, blank=True)
    listing_title = models.CharField(max_length=90, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "تصمیم بررسی"
        verbose_name_plural = "تصمیم‌های بررسی"

    def __str__(self):
        return f"{self.get_decision_display()} — {self.listing_title}"
