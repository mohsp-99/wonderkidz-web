from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.dates import jalali
from apps.listings.models import Listing, Report

from .models import Conversation, Message

SAFETY_SYSTEM_MSG = (
    "⚠️ اگر طرف مقابل از شما خواست بیعانه یا «هزینهٔ رزرو» کارت‌به‌کارت کنید، "
    "معامله را ادامه ندهید و گزارش کنید."
)


def _user_conversations(user):
    return (
        Conversation.objects.filter(Q(buyer=user) | Q(seller=user))
        .select_related("listing", "listing__category", "buyer", "seller")
        .order_by("-last_message_at")
    )


def _inbox_items(user):
    items = []
    for c in _user_conversations(user):
        last = c.last_message()
        items.append(
            {
                "conv": c,
                "other": c.other(user),
                "last": last,
                "last_is_mine": bool(last and last.sender_id == user.id),
                "unread": c.unread_for(user),
            }
        )
    return items


def _get_participant_conversation(request, pk):
    conv = get_object_or_404(
        Conversation.objects.select_related("listing", "listing__category", "buyer", "seller"), pk=pk
    )
    if request.user.id not in (conv.buyer_id, conv.seller_id):
        return None
    return conv


def _mark_read(conv, user):
    conv.messages.filter(is_read=False).exclude(sender=user).update(is_read=True)


def _grouped_messages(conv):
    """Group messages by Jalali day for the .msg-day separators."""
    groups = []
    current_key = None
    for m in conv.messages.select_related("sender").order_by("created_at"):
        key = timezone.localtime(m.created_at).date()
        if key != current_key:
            groups.append({"label": jalali(m.created_at, "%A %d %B"), "messages": []})
            current_key = key
        groups[-1]["messages"].append(m)
    return groups


def _thread_context(request, conv):
    user = request.user
    listing = conv.listing
    return {
        "conv": conv,
        "other": conv.other(user),
        "groups": _grouped_messages(conv),
        "listing": listing,
        "compose_disabled": conv.is_closed or listing.status in (Listing.Status.SOLD, Listing.Status.REMOVED),
        "my_feedback": conv.buyer_feedback if user.id == conv.buyer_id else conv.seller_feedback,
        "report_reasons": Report.Reason.choices,
    }


@login_required
def inbox(request):
    items = _inbox_items(request.user)
    unread_total = sum(i["unread"] for i in items)
    return render(
        request,
        "chat/inbox.html",
        {"items": items, "unread_total": unread_total, "conv": None},
    )


@login_required
def start(request, code):
    listing = get_object_or_404(Listing.objects.select_related("owner"), code=code)
    if listing.owner_id == request.user.id:
        flash.info(request, "این آگهی متعلق به خود شماست.")
        return redirect(listing.get_absolute_url())
    if not listing.is_live or not listing.allow_chat:
        flash.warning(request, "چت برای این آگهی فعال نیست.")
        return redirect(listing.get_absolute_url())
    if request.user.is_banned:
        flash.error(request, "حساب شما محدود شده است و امکان شروع چت ندارد.")
        return redirect(listing.get_absolute_url())
    conv, created = Conversation.objects.get_or_create(
        listing=listing, buyer=request.user, defaults={"seller": listing.owner}
    )
    if created:
        Message.objects.create(conversation=conv, sender=None, is_system=True, is_read=True, body=SAFETY_SYSTEM_MSG)
    return redirect("chat:thread", pk=conv.pk)


@login_required
def thread(request, pk):
    conv = _get_participant_conversation(request, pk)
    if conv is None:
        return HttpResponseForbidden("دسترسی ندارید.")
    _mark_read(conv, request.user)
    items = _inbox_items(request.user)
    ctx = _thread_context(request, conv)
    ctx.update({"items": items, "unread_total": sum(i["unread"] for i in items)})
    return render(request, "chat/thread.html", ctx)


@login_required
def messages_fragment(request, pk):
    conv = _get_participant_conversation(request, pk)
    if conv is None:
        return HttpResponseForbidden("دسترسی ندارید.")
    _mark_read(conv, request.user)
    return render(request, "chat/_messages.html", _thread_context(request, conv))


@login_required
@require_POST
def send(request, pk):
    conv = _get_participant_conversation(request, pk)
    if conv is None:
        return HttpResponseForbidden("دسترسی ندارید.")
    ctx = _thread_context(request, conv)
    if ctx["compose_disabled"]:
        return render(request, "chat/_messages.html", ctx, status=409)
    body = (request.POST.get("body") or "").strip()[:2000]
    if body:
        is_first_buyer_msg = (
            request.user.id == conv.buyer_id
            and not conv.messages.filter(sender=conv.buyer).exists()
        )
        Message.objects.create(conversation=conv, sender=request.user, body=body)
        conv.last_message_at = timezone.now()
        conv.save(update_fields=["last_message_at"])
        if is_first_buyer_msg and conv.seller.notify_chat:
            try:
                from apps.accounts.sms import send_sms

                send_sms(
                    conv.seller.phone,
                    f"وندرکیدز: پیام جدیدی دربارهٔ آگهی «{conv.listing.title}» دارید. {request.build_absolute_uri(conv.get_absolute_url())}",
                )
            except Exception:  # SMS is best-effort
                pass
        ctx = _thread_context(request, conv)
    return render(request, "chat/_messages.html", ctx)


@login_required
@require_POST
def feedback(request, pk):
    conv = _get_participant_conversation(request, pk)
    if conv is None:
        return HttpResponseForbidden("دسترسی ندارید.")
    value = request.POST.get("value")
    if value not in ("good", "bad"):
        return HttpResponseBadRequest("مقدار نامعتبر")
    if request.user.id == conv.buyer_id:
        conv.buyer_feedback = value
    else:
        conv.seller_feedback = value
    conv.save(update_fields=["buyer_feedback", "seller_feedback"])
    if value == "good":
        flash.success(request, "ممنون از بازخوردتان. خوشحالیم که معامله خوب پیش رفت.")
    else:
        flash.warning(request, "متأسفیم. اگر مشکلی پیش آمده، لطفاً آگهی یا گفت‌وگو را گزارش کنید تا بررسی شود.")
    return redirect("chat:thread", pk=conv.pk)
