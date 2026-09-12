from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .gateways import get_gateway
from .models import Payment, Plan


@login_required
def plans(request):
    active = Plan.objects.filter(is_active=True).order_by("price")
    listing = None
    code = request.GET.get("listing")
    if code:
        from apps.listings.models import Listing

        listing = Listing.objects.filter(code=code, owner=request.user).first()
    return render(request, "payments/plans.html", {"plans": active, "listing": listing})


@login_required
@require_POST
def start(request, plan_id):
    plan = get_object_or_404(Plan, pk=plan_id, is_active=True)
    listing = None
    code = request.POST.get("listing")
    if code:
        from apps.listings.models import Listing

        listing = Listing.objects.filter(code=code, owner=request.user).first()
    gateway = get_gateway()
    payment = Payment.objects.create(
        user=request.user, plan=plan, listing=listing, amount=plan.price, gateway=gateway.name
    )
    callback_url = request.build_absolute_uri("/pay/callback/") + f"?payment={payment.pk}"
    url = gateway.start(payment, callback_url)
    if not url:
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status"])
        messages.error(request, "اتصال به درگاه پرداخت برقرار نشد. لطفاً کمی بعد دوباره تلاش کنید.")
        return redirect("payments:result", pk=payment.pk)
    return redirect(url)


def _apply_plan(payment):
    plan = payment.plan
    now = timezone.now()
    if plan.kind == Plan.Kind.PROMOTE and payment.listing_id:
        listing = payment.listing
        listing.is_promoted = True
        listing.promoted_until = now + timezone.timedelta(days=plan.duration_days)
        listing.save(update_fields=["is_promoted", "promoted_until"])
    elif plan.kind == Plan.Kind.SUBSCRIPTION:
        user = payment.user
        user.listing_cap += 20
        user.save(update_fields=["listing_cap"])
    elif plan.kind == Plan.Kind.BADGE:
        user = payment.user
        if user.account_type == user.AccountType.PARENT:
            user.account_type = user.AccountType.PRO
            user.save(update_fields=["account_type"])


@csrf_exempt  # gateways POST back (IDPay) without our CSRF token
def callback(request):
    src = request.POST if request.method == "POST" else request.GET
    payment = None
    if src.get("payment") or request.GET.get("payment"):
        payment = Payment.objects.filter(pk=src.get("payment") or request.GET.get("payment")).first()
    if payment is None:
        authority = src.get("Authority") or src.get("id") or src.get("authority")
        if authority:
            payment = Payment.objects.filter(authority=authority).first()
    if payment is None:
        raise Http404
    if payment.status == Payment.Status.PENDING:
        ok, ref_id = get_gateway().verify(payment, request)
        with transaction.atomic():
            if ok:
                payment.status = Payment.Status.PAID
                payment.ref_id = ref_id
                payment.paid_at = timezone.now()
                payment.save(update_fields=["status", "ref_id", "paid_at"])
                _apply_plan(payment)
            else:
                canceled = src.get("status") == "cancel" or src.get("Status") == "NOK"
                payment.status = Payment.Status.CANCELED if canceled else Payment.Status.FAILED
                payment.save(update_fields=["status"])
    return redirect("payments:result", pk=payment.pk)


@login_required
def fake_gateway_page(request, pk):
    payment = get_object_or_404(Payment, pk=pk, user=request.user, gateway="fake")
    return render(request, "payments/fake_gateway.html", {"payment": payment})


@login_required
def result(request, pk):
    payment = get_object_or_404(Payment, pk=pk, user=request.user)
    return render(request, "payments/result.html", {"payment": payment})
