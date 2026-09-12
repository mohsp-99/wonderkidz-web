from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.catalog.models import City
from apps.core.text import to_en_digits
from apps.listings.models import Listing, SavedListing

from .forms import AccountForm, OTPForm, PhoneForm
from .models import OTPCode, SavedSearch, User
from .sms import send_otp

SESSION_PHONE = "otp_phone"
SESSION_NEXT = "otp_next"


# ---- helpers ---------------------------------------------------------------
def _safe_next(request, fallback=None):
    nxt = request.POST.get("next") or request.GET.get("next") or request.session.get(SESSION_NEXT)
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return fallback or reverse("accounts:profile")


def _rate_limited(phone) -> bool:
    key = f"otp-rate:{phone}"
    count = cache.get(key, 0)
    if count >= settings.OTP_RATE_LIMIT_PER_HOUR:
        return True
    cache.set(key, count + 1, 60 * 60)
    return False


def _issue_code(request, phone) -> bool:
    if _rate_limited(phone):
        messages.error(request, "تعداد درخواست کد بیش از حد مجاز است. لطفاً یک ساعت دیگر دوباره تلاش کنید.")
        return False
    OTPCode.objects.filter(phone=phone, used=False).update(used=True)
    otp = OTPCode.generate(phone)
    send_otp(phone, otp.code)
    request.session[SESSION_PHONE] = phone
    return True


# ---- auth ------------------------------------------------------------------
def login_view(request):
    if request.user.is_authenticated:
        return redirect(_safe_next(request))
    nxt = request.GET.get("next") or request.POST.get("next") or ""
    if nxt:
        request.session[SESSION_NEXT] = nxt
    form = PhoneForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        phone = form.cleaned_data["phone"]
        if _issue_code(request, phone):
            return redirect("accounts:verify")
    return render(request, "accounts/login.html", {"form": form, "next": nxt})


def verify_view(request):
    phone = request.session.get(SESSION_PHONE)
    if not phone:
        return redirect("accounts:login")
    form = OTPForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        code = form.cleaned_data["code"]
        otp = OTPCode.objects.filter(phone=phone, used=False).order_by("-created_at").first()
        dev_ok = bool(settings.OTP_DEV_CODE) and code == to_en_digits(settings.OTP_DEV_CODE)
        if dev_ok or (otp and otp.is_valid and otp.code == code):
            if otp:
                otp.used = True
                otp.save(update_fields=["used"])
            user, created = User.objects.get_or_create(phone=phone, defaults={"is_verified": True})
            if user.is_banned:
                messages.error(request, "این حساب مسدود شده است." + (f" دلیل: {user.ban_reason}" if user.ban_reason else ""))
                return redirect("accounts:login")
            if not user.is_verified:
                user.is_verified = True
            user.last_seen = timezone.now()
            user.save(update_fields=["is_verified", "last_seen"])
            auth_login(request, user)
            request.session.pop(SESSION_PHONE, None)
            nxt = _safe_next(request)
            request.session.pop(SESSION_NEXT, None)
            if created:
                messages.success(request, "خوش آمدید! حساب شما با شمارهٔ تأییدشده ساخته شد.")
            return redirect(nxt)
        if otp and not otp.is_valid:
            messages.error(request, "کد منقضی شده است. کد تازه‌ای درخواست کنید.")
        else:
            if otp:
                otp.attempts += 1
                otp.save(update_fields=["attempts"])
            messages.error(request, "کد وارد شده درست نیست.")
    return render(
        request,
        "accounts/verify.html",
        {"form": form, "phone": phone, "OTP_TTL_SECONDS": settings.OTP_TTL_SECONDS},
    )


@require_POST
def resend_view(request):
    phone = request.session.get(SESSION_PHONE)
    if not phone:
        return redirect("accounts:login")
    if _issue_code(request, phone):
        messages.info(request, "کد تازه پیامک شد.")
    return redirect("accounts:verify")


@require_POST
def logout_view(request):
    auth_logout(request)
    messages.info(request, "از حساب خارج شدید.")
    return redirect("listings:home")


# ---- profile ---------------------------------------------------------------
@login_required
def profile_view(request):
    user = request.user
    base = user.listings.select_related("category", "district").prefetch_related("images").annotate(
        chat_count=Count("conversations", distinct=True)
    )
    active = base.filter(status__in=[Listing.Status.LIVE, Listing.Status.EXPIRED, Listing.Status.PAUSED]).order_by(
        "-published_at", "-created_at"
    )
    pending = base.filter(status__in=[Listing.Status.PENDING, Listing.Status.REJECTED, Listing.Status.DRAFT]).order_by(
        "-created_at"
    )
    sold = base.filter(status=Listing.Status.SOLD).order_by("-sold_at")
    saved = (
        SavedListing.objects.filter(user=user, listing__status=Listing.Status.LIVE)
        .select_related("listing__category", "listing__district", "listing__owner")
        .order_by("-created_at")
    )
    week_ago = timezone.now() - timezone.timedelta(days=7)
    week_views = sum(x.views_count for x in active)  # views_count is lifetime; good enough for a first version
    ctx = {
        "profile_user": user,
        "active": active,
        "pending": pending,
        "sold": sold,
        "saved": saved,
        "saved_searches": user.saved_searches.all(),
        "week_views": week_views,
        "week_ago": week_ago,
        "form": AccountForm(instance=user),
        "pending_count": pending.filter(status=Listing.Status.PENDING).count(),
    }
    return render(request, "accounts/profile.html", ctx)


@login_required
@require_POST
def account_edit_view(request):
    form = AccountForm(request.POST, instance=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, "تغییرات حساب ذخیره شد.")
        return redirect(reverse("accounts:profile") + "#t-account")
    for field, errs in form.errors.items():
        for e in errs:
            messages.error(request, e)
    return redirect(reverse("accounts:profile") + "#t-account")


@login_required
@require_POST
def saved_search_delete(request, pk):
    ss = get_object_or_404(SavedSearch, pk=pk, user=request.user)
    ss.delete()
    messages.info(request, "جستجوی ذخیره‌شده حذف شد.")
    return redirect(reverse("accounts:profile") + "#t-saved")


@require_POST
def set_city(request):
    slug = request.POST.get("city", "")
    city = City.objects.filter(slug=slug, is_active=True).first()
    if city:
        request.session["city"] = city.slug
    ref = request.META.get("HTTP_REFERER", "")
    if ref and url_has_allowed_host_and_scheme(ref, allowed_hosts={request.get_host()}):
        return redirect(ref)
    return redirect("listings:home")


def public_profile_view(request, pk):
    seller = get_object_or_404(User, pk=pk, is_active=True)
    listings = (
        seller.listings.filter(status=Listing.Status.LIVE)
        .select_related("category", "district", "owner")
        .prefetch_related("images")
        .order_by("-published_at")
    )
    return render(
        request,
        "accounts/public_profile.html",
        {"seller": seller, "listings": listings, "active_count": listings.count(), "sold_count": seller.sold_count},
    )
