"""Operator-panel helpers: stats, decision log, seller notifications."""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F
from django.utils import timezone

from apps.chat.models import Conversation
from apps.listings.models import Listing, PhoneReveal, Report

from .models import ModerationDecision

REJECT_REASONS = [
    "در عکس‌ها چهرهٔ کودک دیده می‌شود",
    "عکس نامفهوم یا بی‌کیفیت است",
    "دسته‌بندی اشتباه است",
    "کالای خارج از حوزهٔ اسباب‌بازی",
    "کالای ناایمن یا فراخوان‌شده",
    "شماره تماس یا لینک در متن آگهی",
    "قیمت غیرواقعی / مشکوک به کلاهبرداری",
    "یادداشت بهداشتی خالی است",
    "عکس ناکافی",
    "متن دیگر…",
]


def notify(user, text):
    """Best-effort SMS to a user. The SMS module is owned by the accounts app; failures never break moderation."""
    if not user or not getattr(user, "phone", None):
        return
    try:
        from apps.accounts.sms import send_sms

        send_sms(user.phone, text)
    except Exception:
        pass


def record_decision(operator, decision, listing=None, report=None, target_user=None, reason=""):
    return ModerationDecision.objects.create(
        operator=operator,
        decision=decision,
        listing=listing,
        report=report,
        target_user=target_user or (listing.owner if listing else None),
        reason=reason[:200],
        listing_title=(listing.title if listing else (report.target_title if report else ""))[:90],
    )


def approve_listing(listing, operator):
    listing.publish(by=operator)
    record_decision(operator, ModerationDecision.Decision.APPROVE, listing=listing)
    if listing.owner.notify_moderation:
        notify(listing.owner, f"وندرکیدز: آگهی «{listing.title}» تأیید و منتشر شد.")


def reject_listing(listing, operator, reason, note=""):
    listing.reject(reason, note, by=operator)
    record_decision(operator, ModerationDecision.Decision.REJECT, listing=listing, reason=reason)
    if listing.owner.notify_moderation:
        msg = f"وندرکیدز: آگهی «{listing.title}» تأیید نشد. دلیل: {reason}"
        if note:
            msg += f" — {note}"
        msg += " می‌توانید آگهی را اصلاح و دوباره ارسال کنید."
        notify(listing.owner, msg)


def takedown_listing(listing, operator, reason="حذف توسط اپراتور"):
    listing.status = Listing.Status.REMOVED
    listing.reviewed_by = operator
    listing.reviewed_at = timezone.now()
    listing.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
    record_decision(operator, ModerationDecision.Decision.TAKEDOWN, listing=listing, reason=reason)
    notify(listing.owner, f"وندرکیدز: آگهی «{listing.title}» به دلیل «{reason}» حذف شد.")


def ban_user(user, operator, reason="", report=None):
    user.is_banned = True
    user.ban_reason = reason[:200]
    user.save(update_fields=["is_banned", "ban_reason"])
    for listing in user.listings.filter(status__in=[Listing.Status.LIVE, Listing.Status.PENDING]):
        listing.status = Listing.Status.REMOVED
        listing.save(update_fields=["status", "updated_at"])
    record_decision(operator, ModerationDecision.Decision.BAN, target_user=user, report=report, reason=reason)
    notify(user, "وندرکیدز: حساب شما به دلیل نقض قوانین مسدود شد.")


def unban_user(user, operator):
    user.is_banned = False
    user.ban_reason = ""
    user.save(update_fields=["is_banned", "ban_reason"])
    record_decision(operator, ModerationDecision.Decision.DISMISS, target_user=user, reason="رفع مسدودی")


def warn_user(user, operator, reason="", report=None, listing=None):
    user.warnings_count = F("warnings_count") + 1
    user.save(update_fields=["warnings_count"])
    user.refresh_from_db(fields=["warnings_count"])
    record_decision(operator, ModerationDecision.Decision.WARN, target_user=user, report=report, listing=listing, reason=reason)
    notify(user, f"وندرکیدز: تذکر — {reason or 'لطفاً قوانین پلتفرم را رعایت کنید.'}")


def resolve_report(report, operator, action):
    """Apply one of the panel actions to a report and close it."""
    report.handled_by = operator
    report.handled_at = timezone.now()
    listing = report.listing
    conv = report.conversation
    if action == "takedown_ban":
        target = listing.owner if listing else None
        if listing:
            takedown_listing(listing, operator, reason=report.get_reason_display())
        if target:
            ban_user(target, operator, reason=report.get_reason_display(), report=report)
        report.status = Report.Status.RESOLVED
        report.resolution = "حذف آگهی + مسدودسازی"
    elif action == "warn":
        target = listing.owner if listing else (conv.other(report.reporter) if conv else None)
        if target:
            warn_user(target, operator, reason=report.get_reason_display(), report=report, listing=listing)
        report.status = Report.Status.RESOLVED
        report.resolution = "تذکر به فروشنده" if listing else "اخطار به کاربر"
    elif action == "takedown":
        if listing:
            takedown_listing(listing, operator, reason=report.get_reason_display())
        report.status = Report.Status.RESOLVED
        report.resolution = "حذف آگهی"
    else:  # dismiss
        report.status = Report.Status.DISMISSED
        report.resolution = "بی‌اشکال"
        record_decision(operator, ModerationDecision.Decision.DISMISS, report=report, listing=listing, reason=report.get_reason_display())
    report.save()
    return report


def panel_stats():
    User = get_user_model()
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    pending = Listing.objects.filter(status=Listing.Status.PENDING)
    oldest = pending.order_by("submitted_at").first()
    oldest_minutes = int((now - oldest.submitted_at).total_seconds() // 60) if oldest and oldest.submitted_at else 0

    reviewed = Listing.objects.filter(reviewed_at__gte=week_ago, submitted_at__isnull=False, reviewed_at__isnull=False)
    avg_delta = reviewed.annotate(
        d=ExpressionWrapper(F("reviewed_at") - F("submitted_at"), output_field=DurationField())
    ).aggregate(a=Avg("d"))["a"]
    avg_minutes = int(avg_delta.total_seconds() // 60) if avg_delta else None

    chats_week = Conversation.objects.filter(created_at__gte=week_ago).count()
    reveals_week = PhoneReveal.objects.filter(created_at__gte=week_ago).count()
    open_reports = Report.objects.filter(status=Report.Status.OPEN)

    return {
        "live_count": Listing.objects.filter(status=Listing.Status.LIVE).count(),
        "live_week": Listing.objects.filter(status=Listing.Status.LIVE, published_at__gte=week_ago).count(),
        "pending_count": pending.count(),
        "oldest_minutes": oldest_minutes,
        "sla_hours": settings.MODERATION_SLA_HOURS,
        "open_reports": open_reports.count(),
        "urgent_reports": open_reports.filter(priority=Report.Priority.URGENT).count(),
        "contacts_week": chats_week + reveals_week,
        "chats_week": chats_week,
        "reveals_week": reveals_week,
        "new_users_week": User.objects.filter(date_joined__gte=week_ago).count(),
        "avg_minutes": avg_minutes,
        "decisions_today": ModerationDecision.objects.filter(created_at__date=timezone.localdate()).count(),
    }


def checklist_for(listing):
    """Derive the operator checklist from auto flags. Returns list of (icon, label)."""
    codes = {f.get("code") for f in (listing.auto_flags or [])}
    child = "child_photo" in codes
    return [
        ("✅" if "category" not in codes else "❌", "عنوان و دسته درست است"),
        ("✅" if "price" not in codes else "❌", "قیمت منطقی است"),
        ("❌" if child else "⚠️", "عکس کودک ندارد" if child else "عکس کودک ندارد (بررسی چشمی)"),
        ("✅" if "prohibited" not in codes else "❌", "کالای ممنوعه نیست"),
        ("✅" if "contact" not in codes else "❌", "شماره/لینک در متن ندارد"),
        ("✅" if listing.hygiene_note.strip() and "hygiene" not in codes else "❌", "یادداشت بهداشتی پر است"),
        ("⚠️" if "few_images" in codes else "✅", "فقط یک عکس دارد" if "few_images" in codes else "تعداد عکس کافی است"),
    ]


def weekly_series(qs, field, weeks=8):
    """[(week_start_date, count), ...] oldest→newest for the last N weeks."""
    now = timezone.localtime(timezone.now())
    start_of_week = (now - timedelta(days=(now.weekday() + 2) % 7)).replace(hour=0, minute=0, second=0, microsecond=0)  # Saturday
    out = []
    for i in range(weeks - 1, -1, -1):
        ws = start_of_week - timedelta(weeks=i)
        we = ws + timedelta(weeks=1)
        out.append((ws, qs.filter(**{f"{field}__gte": ws, f"{field}__lt": we}).count()))
    return out


def top_by(field, limit=8):
    return (
        Listing.objects.filter(status=Listing.Status.LIVE)
        .values(name=F(f"{field}__name"))
        .annotate(n=Count("id"))
        .order_by("-n")[:limit]
    )
