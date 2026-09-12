from functools import wraps

from django.contrib import messages as flash
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.chat.models import Conversation
from apps.listings.models import Listing, PhoneReveal, Report

from . import services
from .models import ModerationDecision

User = get_user_model()


def operator_required(view):
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/login/?next={request.path}")
        if not request.user.is_staff:
            flash.error(request, "این بخش فقط برای اپراتورهای وندرکیدز است.")
            return redirect("listings:home")
        return view(request, *args, **kwargs)

    return _wrapped


def _badge(cls, text):
    return HttpResponse(f'<span class="badge {cls}">{text}</span>')


def _queue_items(qs):
    now = timezone.now()
    items = []
    for lst in qs:
        wait = int((now - (lst.submitted_at or lst.created_at)).total_seconds() // 60)
        items.append({"l": lst, "wait_minutes": wait, "checklist": services.checklist_for(lst), "flags": lst.auto_flags or []})
    return items


@operator_required
def queue(request):
    pending = (
        Listing.objects.filter(status=Listing.Status.PENDING)
        .select_related("owner", "category", "category__parent", "district", "brand")
        .prefetch_related("images")
        .order_by("submitted_at", "created_at")
    )
    return render(
        request,
        "panel/queue.html",
        {
            "stats": services.panel_stats(),
            "items": _queue_items(pending),
            "reject_reasons": services.REJECT_REASONS,
            "listing_stats_url": True,
        },
    )


@operator_required
@require_POST
def approve(request, pk):
    listing = get_object_or_404(Listing, pk=pk)
    if listing.status != Listing.Status.PENDING:
        return _badge("badge-pending", "قبلاً بررسی شده") if request.htmx else redirect("panel:queue")
    services.approve_listing(listing, request.user)
    if request.htmx:
        return _badge("badge-live", "✓ تأیید شد")
    flash.success(request, f"آگهی «{listing.title}» منتشر شد.")
    return redirect("panel:queue")


@operator_required
@require_POST
def reject(request, pk):
    listing = get_object_or_404(Listing, pk=pk)
    reason = (request.POST.get("reason") or "").strip() or "متن دیگر…"
    note = (request.POST.get("note") or "").strip()
    if listing.status != Listing.Status.PENDING:
        return _badge("badge-pending", "قبلاً بررسی شده") if request.htmx else redirect("panel:queue")
    services.reject_listing(listing, request.user, reason, note)
    if request.htmx:
        return _badge("badge-sold", "✗ رد شد")
    flash.warning(request, f"آگهی «{listing.title}» رد شد.")
    return redirect("panel:queue")


@operator_required
def reports(request):
    status = request.GET.get("status", "open")
    qs = Report.objects.select_related("reporter", "listing", "listing__district", "conversation", "handled_by").order_by(
        "-priority", "-created_at"
    )
    qs = qs.filter(status=Report.Status.OPEN) if status == "open" else qs.exclude(status=Report.Status.OPEN)
    rows = []
    for r in qs[:200]:
        if r.listing_id:
            same = Report.objects.filter(listing_id=r.listing_id, status=Report.Status.OPEN).count()
        else:
            same = Report.objects.filter(conversation_id=r.conversation_id, status=Report.Status.OPEN).count()
        rows.append({"r": r, "same": same})
    return render(request, "panel/reports.html", {"rows": rows, "status": status, "stats": services.panel_stats()})


@operator_required
@require_POST
def resolve_report(request, pk):
    report = get_object_or_404(Report, pk=pk)
    action = request.POST.get("action", "dismiss")
    if report.status != Report.Status.OPEN:
        return _badge("badge-pending", "قبلاً رسیدگی شده") if request.htmx else redirect("panel:reports")
    services.resolve_report(report, request.user, action)
    if request.htmx:
        ok = report.status == Report.Status.DISMISSED
        return _badge("badge-live" if ok else "badge-sold", ("✓ بی‌اشکال" if ok else f"✓ {report.resolution}"))
    flash.success(request, f"گزارش رسیدگی شد: {report.resolution}")
    return redirect("panel:reports")


@operator_required
def users(request):
    q = (request.GET.get("q") or "").strip()
    qs = User.objects.annotate(
        n_listings=Count("listings", distinct=True),
        n_live=Count("listings", filter=Q(listings__status=Listing.Status.LIVE), distinct=True),
    ).order_by("-date_joined")
    if q:
        qs = qs.filter(Q(phone__icontains=q) | Q(display_name__icontains=q))
    flt = request.GET.get("f")
    if flt == "banned":
        qs = qs.filter(is_banned=True)
    elif flt == "staff":
        qs = qs.filter(is_staff=True)
    return render(request, "panel/users.html", {"users": qs[:200], "q": q, "f": flt})


@operator_required
def user_detail(request, pk):
    u = get_object_or_404(User, pk=pk)
    listings = u.listings.select_related("category", "district").order_by("-created_at")
    reports_about = Report.objects.filter(Q(listing__owner=u) | Q(conversation__seller=u) | Q(conversation__buyer=u)).exclude(reporter=u).select_related("listing", "reporter").order_by("-created_at")[:50]
    decisions = ModerationDecision.objects.filter(Q(target_user=u) | Q(listing__owner=u)).select_related("operator").order_by("-created_at")[:50]
    convs = Conversation.objects.filter(Q(buyer=u) | Q(seller=u)).count()
    reveals = PhoneReveal.objects.filter(user=u).count()
    return render(
        request,
        "panel/user_detail.html",
        {"u": u, "listings": listings, "reports_about": reports_about, "decisions": decisions, "convs": convs, "reveals": reveals},
    )


@operator_required
@require_POST
def ban_user(request, pk):
    u = get_object_or_404(User, pk=pk)
    if u.is_superuser or u == request.user:
        flash.error(request, "این حساب قابل مسدودسازی نیست.")
        return redirect("panel:user_detail", pk=pk)
    if u.is_banned:
        services.unban_user(u, request.user)
        flash.success(request, f"مسدودی «{u.name}» برداشته شد.")
    else:
        services.ban_user(u, request.user, reason=(request.POST.get("reason") or "").strip())
        flash.warning(request, f"حساب «{u.name}» مسدود شد و آگهی‌های فعالش برداشته شد.")
    return redirect("panel:user_detail", pk=pk)


@operator_required
def listings(request):
    status = request.GET.get("status", "")
    q = (request.GET.get("q") or "").strip()
    qs = Listing.objects.select_related("owner", "category", "district").order_by("-created_at")
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(code__icontains=q) | Q(owner__phone__icontains=q))
    counts = dict(Listing.objects.values_list("status").annotate(n=Count("id")))
    return render(
        request,
        "panel/listings.html",
        {"rows": qs[:200], "status": status, "q": q, "statuses": Listing.Status.choices, "counts": counts},
    )


@operator_required
@require_POST
def takedown(request, pk):
    listing = get_object_or_404(Listing, pk=pk)
    reason = (request.POST.get("reason") or "").strip() or "حذف توسط اپراتور"
    services.takedown_listing(listing, request.user, reason=reason)
    if request.htmx:
        return _badge("badge-sold", "✓ حذف شد")
    flash.warning(request, f"آگهی «{listing.title}» حذف شد.")
    return redirect(request.POST.get("next") or "panel:listings")


@operator_required
def stats(request):
    per_status = [(label, Listing.objects.filter(status=val).count()) for val, label in Listing.Status.choices]
    signups = services.weekly_series(User.objects.all(), "date_joined")
    chats = services.weekly_series(Conversation.objects.all(), "created_at")
    reveals = services.weekly_series(PhoneReveal.objects.all(), "created_at")
    published = services.weekly_series(Listing.objects.all(), "published_at")
    contacts = [(s[0], s[1] + r[1], s[1], r[1], p[1]) for s, r, p in zip(chats, reveals, published)]
    return render(
        request,
        "panel/stats.html",
        {
            "stats": services.panel_stats(),
            "per_status": per_status,
            "signups": signups,
            "contacts": contacts,
            "top_categories": services.top_by("category"),
            "top_districts": services.top_by("district"),
            "total_users": User.objects.count(),
            "verified_users": User.objects.filter(is_verified=True).count(),
        },
    )


@operator_required
def decisions(request):
    today = timezone.localdate()
    qs = ModerationDecision.objects.select_related("operator", "listing").order_by("-created_at")
    today_rows = qs.filter(created_at__date=today)
    week_rows = qs.filter(created_at__date__lt=today, created_at__gte=timezone.now() - timezone.timedelta(days=7))[:200]
    approved = today_rows.filter(decision=ModerationDecision.Decision.APPROVE).count()
    rejected = today_rows.filter(decision=ModerationDecision.Decision.REJECT).count()
    return render(
        request,
        "panel/decisions.html",
        {"today_rows": today_rows, "week_rows": week_rows, "approved": approved, "rejected": rejected, "total_today": today_rows.count()},
    )
