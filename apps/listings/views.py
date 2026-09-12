import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Case, Count, IntegerField, When
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accounts.models import SavedSearch
from apps.catalog.models import AGE_EMOJI, AGE_SHORT, AgeRange, Brand, Category, City, District
from apps.core.images import InvalidImage, process_upload
from apps.core.text import format_price, normalize, parse_int, to_fa_digits

from . import services
from .forms import ListingForm, ReportForm, validate_images
from .models import Listing, ListingImage, PhoneReveal, Report, SavedListing

AGE_LABELS = dict(AgeRange.choices)
COND_LABELS = dict(Listing.Condition.choices)
STATIC_PAGES = {
    "about": "دربارهٔ ما",
    "posting-guide": "راهنمای ثبت آگهی",
    "safety": "نکات ایمنی خرید",
    "terms": "قوانین و شرایط",
    "privacy": "حریم خصوصی",
    "faq": "سؤالات متداول",
}


def _live(city=None):
    qs = Listing.objects.filter(status=Listing.Status.LIVE).select_related(
        "category", "category__parent", "district", "owner", "brand"
    )
    if city:
        qs = qs.filter(city=city)
    return qs


# ---------------------------------------------------------------- home
def home(request):
    city = City.get_current(request)
    live = _live(city)
    roots = list(Category.objects.filter(parent__isnull=True).order_by("order"))
    counts = dict(
        live.values_list("category__parent_id").annotate(c=Count("id")).values_list("category__parent_id", "c")
    )
    counts_direct = dict(live.values_list("category_id").annotate(c=Count("id")).values_list("category_id", "c"))
    for r in roots:
        r.live_count = counts.get(r.id, 0) + counts_direct.get(r.id, 0)
    from apps.accounts.models import User

    ctx = {
        "city": city,
        "roots": roots,
        "latest": live.order_by("-is_promoted", "-published_at")[:12],
        "live_count": live.count(),
        "district_count": District.objects.filter(city=city, is_active=True).count() if city else 0,
        "district_names": "، ".join(
            District.objects.filter(city=city, is_active=True).order_by("order").values_list("name", flat=True)[:3]
        )
        if city
        else "",
        "sold_count": Listing.objects.filter(status=Listing.Status.SOLD).count(),
        "user_count": User.objects.filter(is_active=True).count(),
        "ages": [(k, v, AGE_EMOJI[k]) for k, v in AgeRange.choices],
        "brands": Brand.objects.filter(is_featured=True).order_by("order"),
    }
    return render(request, "listings/home.html", ctx)


# ---------------------------------------------------------------- search
def _apply_filters(request, qs, category=None):
    g = request.GET
    q = g.get("q", "").strip()
    if q:
        for word in normalize(q).split():
            qs = qs.filter(search_text__icontains=word)
    if category:
        qs = qs.filter(category_id__in=category.descendant_ids())
    ages = [a for a in g.getlist("age") if a in AGE_LABELS]
    if ages:
        qs = qs.filter(age_range__in=ages)
    conds = [c for c in g.getlist("cond") if c in COND_LABELS]
    if conds:
        qs = qs.filter(condition__in=conds)
    if g.get("complete") == "1":
        qs = qs.filter(is_complete=True, missing_parts=False)
    if g.get("box") == "1":
        qs = qs.filter(has_box=True)
    mn, mx = parse_int(g.get("min")), parse_int(g.get("max"))
    if mn:
        qs = qs.filter(price__gte=mn)
    if mx:
        qs = qs.filter(price__lte=mx)
    brands = g.getlist("brand")
    if brands:
        qs = qs.filter(brand__slug__in=brands)
    dists = g.getlist("dist")
    if dists:
        qs = qs.filter(district__slug__in=dists)
    if g.get("photo") == "1":
        qs = qs.filter(images__isnull=False).distinct()
    if g.get("official") == "1":
        qs = qs.filter(owner__account_type="official")
    if g.get("verified") == "1":
        qs = qs.filter(owner__is_verified=True)
    if g.get("chat") == "1":
        qs = qs.filter(allow_chat=True)
    return qs


def _apply_sort(request, qs):
    sort = request.GET.get("sort", "newest")
    if sort == "cheapest":
        return qs.order_by("price", "-published_at")
    if sort == "expensive":
        return qs.order_by("-price", "-published_at")
    if sort == "nearest" and request.user.is_authenticated and request.user.district_id:
        return qs.annotate(
            near=Case(When(district_id=request.user.district_id, then=0), default=1, output_field=IntegerField())
        ).order_by("near", "-is_promoted", "-published_at")
    return qs.order_by("-is_promoted", "-published_at")


def search(request, category_slug=None, district_slug=None):
    city = City.get_current(request)
    category = None
    slug = category_slug or request.GET.get("cat")
    if slug:
        category = Category.objects.filter(slug=slug).select_related("parent").first()
        if category_slug and not category:
            raise Http404
    g = request.GET
    if district_slug:
        g = g.copy()
        g.setlist("dist", [district_slug])
        request.GET = g

    base = _live(city)
    qs = _apply_sort(request, _apply_filters(request, base, category))
    total = qs.count()

    paginator = Paginator(qs, 24)
    page = paginator.get_page(g.get("page"))

    if request.htmx and g.get("page"):
        return render(request, "listings/_results.html", {"page": page, "category": category})

    # facet counts (on city-wide live listings, ignoring the facet's own filter for simplicity)
    cond_counts = dict(base.values_list("condition").annotate(c=Count("id")).values_list("condition", "c"))
    brand_counts = dict(base.exclude(brand__isnull=True).values_list("brand__slug").annotate(c=Count("id")).values_list("brand__slug", "c"))
    dist_counts = dict(base.values_list("district__slug").annotate(c=Count("id")).values_list("district__slug", "c"))

    roots = list(Category.objects.filter(parent__isnull=True).order_by("order").prefetch_related("children"))
    selected_root = category.root if category else None
    ages_sel = g.getlist("age")
    conds_sel = g.getlist("cond")
    brands_sel = g.getlist("brand")
    dists_sel = g.getlist("dist")

    # applied pills
    pills = []
    if g.get("q"):
        pills.append(("q", None, f"«{g['q']}»"))
    if category:
        pills.append(("cat", None, category.name))
    for a in ages_sel:
        if a in AGE_LABELS:
            pills.append(("age", a, AGE_LABELS[a]))
    for c in conds_sel:
        if c in COND_LABELS:
            pills.append(("cond", c, COND_LABELS[c]))
    if g.get("complete") == "1":
        pills.append(("complete", None, "همهٔ قطعات موجود"))
    if g.get("box") == "1":
        pills.append(("box", None, "جعبهٔ اصلی دارد"))
    if parse_int(g.get("min")):
        pills.append(("min", None, f"از {format_price(parse_int(g.get('min')))} تومان"))
    if parse_int(g.get("max")):
        pills.append(("max", None, f"تا {format_price(parse_int(g.get('max')))} تومان"))
    brand_names = dict(Brand.objects.values_list("slug", "name"))
    for b in brands_sel:
        if b in brand_names:
            pills.append(("brand", b, brand_names[b]))
    dist_names = dict(District.objects.filter(city=city).values_list("slug", "name")) if city else {}
    for d in dists_sel:
        if d in dist_names:
            pills.append(("dist", d, dist_names[d]))
    for key, label in (("photo", "فقط عکس‌دار"), ("official", "فروشگاه وندرکیدز"), ("verified", "فروشندهٔ تأییدشده"), ("chat", "چت فعال")):
        if g.get(key) == "1":
            pills.append((key, None, label))

    title_bits = [category.name if category else "همهٔ اسباب‌بازی‌ها"]
    if len(ages_sel) == 1 and ages_sel[0] in AGE_LABELS:
        title_bits.append(AGE_LABELS[ages_sel[0]])
    if len(dists_sel) == 1 and dists_sel[0] in dist_names:
        title_bits.append(dist_names[dists_sel[0]])
    elif city:
        title_bits.append(city.name)
    seo_title = "، ".join(title_bits)

    median = services.median_price(category) if category else None
    ctx = {
        "city": city,
        "category": category,
        "selected_root": selected_root,
        "roots": roots,
        "page": page,
        "total": total,
        "ages": [(k, AGE_SHORT[k]) for k, _ in AgeRange.choices],
        "ages_sel": ages_sel,
        "conds": Listing.Condition.choices,
        "conds_sel": conds_sel,
        "cond_counts": cond_counts,
        "brands": Brand.objects.order_by("order"),
        "brands_sel": brands_sel,
        "brand_counts": brand_counts,
        "districts": District.objects.filter(city=city, is_active=True).order_by("order") if city else [],
        "dists_sel": dists_sel,
        "dist_counts": dist_counts,
        "pills": pills,
        "seo_title": seo_title,
        "sort": g.get("sort", "newest"),
        "median": median,
        "querystring": g.urlencode(),
        "active_filter_count": len(pills),
    }
    return render(request, "listings/search.html", ctx)


@login_required
@require_POST
def save_search(request):
    qs = request.POST.get("querystring", "")[:500]
    label = request.POST.get("label", "")[:120] or "جستجوی من"
    SavedSearch.objects.get_or_create(user=request.user, querystring=qs, defaults={"label": label})
    messages.success(request, "جستجو ذخیره شد. وقتی آگهی تازه‌ای مطابق آن ثبت شود پیامک می‌گیرید.")
    return redirect(f"{reverse('listings:search')}?{qs}")


# ---------------------------------------------------------------- detail
def _get_listing(code):
    return get_object_or_404(
        Listing.objects.select_related("category", "category__parent", "district", "city", "owner", "brand"), code=code
    )


def detail(request, code, slug=None):
    listing = _get_listing(code)
    is_owner = request.user.is_authenticated and (request.user == listing.owner or request.user.is_staff)
    if not listing.is_live and not is_owner:
        raise Http404
    if slug is not None and slug != listing.slug and listing.slug:
        return redirect(listing.get_absolute_url(), permanent=True)

    if listing.is_live:
        seen = request.session.setdefault("seen", [])
        if listing.code not in seen:
            seen.append(listing.code)
            request.session["seen"] = seen[-200:]
            Listing.objects.filter(pk=listing.pk).update(views_count=listing.views_count + 1)
            listing.views_count += 1

    saved = request.user.is_authenticated and SavedListing.objects.filter(user=request.user, listing=listing).exists()
    revealed = request.user.is_authenticated and PhoneReveal.objects.filter(user=request.user, listing=listing).exists()
    related = (
        _live(listing.city)
        .filter(category_id__in=listing.category.root.descendant_ids())
        .exclude(pk=listing.pk)
        .order_by("-published_at")[:6]
    )
    images = list(listing.images.all())
    jsonld = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": listing.title,
        "description": listing.description[:300],
        "image": [request.build_absolute_uri(i.image.url) for i in images[:4]],
        "brand": listing.brand.name if listing.brand else None,
        "itemCondition": "https://schema.org/NewCondition" if listing.condition == "new" else "https://schema.org/UsedCondition",
        "offers": {
            "@type": "Offer",
            "price": listing.price,
            "priceCurrency": "IRR",
            "availability": "https://schema.org/InStock" if listing.is_live else "https://schema.org/SoldOut",
            "url": request.build_absolute_uri(listing.get_absolute_url()),
        },
    }
    ctx = {
        "listing": listing,
        "images": images,
        "is_owner": is_owner,
        "saved": saved,
        "revealed": revealed,
        "related": related,
        "tips": listing.category.tips(),
        "report_form": ReportForm(),
        "jsonld": json.dumps(jsonld, ensure_ascii=False),
        "owner_active": listing.owner.listings.filter(status=Listing.Status.LIVE).count(),
        "owner_sold": listing.owner.sold_count,
    }
    return render(request, "listings/listing.html", ctx)


@require_POST
def reveal_phone(request, code):
    listing = _get_listing(code)
    if not request.user.is_authenticated:
        if request.htmx:
            resp = HttpResponse()
            resp["HX-Redirect"] = f"{reverse('accounts:login')}?next={listing.get_absolute_url()}"
            return resp
        return redirect(f"{reverse('accounts:login')}?next={listing.get_absolute_url()}")
    if not listing.allow_phone:
        return render(request, "listings/_phone_reveal.html", {"listing": listing, "denied": True})
    key = f"reveal:{request.user.pk}"
    n = cache.get(key, 0)
    if n >= 30:
        return render(request, "listings/_phone_reveal.html", {"listing": listing, "limited": True})
    cache.set(key, n + 1, 3600)
    _, created = PhoneReveal.objects.get_or_create(listing=listing, user=request.user)
    if created and request.user != listing.owner:
        Listing.objects.filter(pk=listing.pk).update(reveals_count=listing.reveals_count + 1)
        listing.reveals_count += 1
    return render(request, "listings/_phone_reveal.html", {"listing": listing, "revealed": True})


@login_required
@require_POST
def toggle_save(request, code):
    listing = _get_listing(code)
    obj, created = SavedListing.objects.get_or_create(user=request.user, listing=listing)
    if not created:
        obj.delete()
    if request.htmx:
        return render(request, "listings/_save_button.html", {"listing": listing, "saved": created})
    return redirect(listing.get_absolute_url())


@login_required
@require_POST
def report(request, code):
    listing = _get_listing(code)
    form = ReportForm(request.POST)
    if form.is_valid():
        rep = form.save(commit=False)
        rep.reporter = request.user
        rep.listing = listing
        if rep.reason in (Report.Reason.SCAM, Report.Reason.CHILD_PHOTO, Report.Reason.PROHIBITED):
            rep.priority = Report.Priority.URGENT
        rep.save()
        messages.success(request, "گزارش شما ثبت شد. اپراتور وندرکیدز بررسی می‌کند. ممنون که به امن ماندن تابلو کمک کردید.")
    else:
        messages.error(request, "دلیل گزارش را انتخاب کنید.")
    return redirect(listing.get_absolute_url())


# ---------------------------------------------------------------- owner actions
def _owned(request, code):
    listing = _get_listing(code)
    if listing.owner != request.user and not request.user.is_staff:
        raise Http404
    return listing


@login_required
@require_POST
def mark_sold(request, code):
    listing = _owned(request, code)
    listing.mark_sold()
    messages.success(request, f"آگهی «{listing.title}» فروخته‌شده علامت خورد. دست شما درد نکند ♻️")
    return redirect(reverse("accounts:profile") + "#t-sold")


@login_required
@require_POST
def renew(request, code):
    listing = _owned(request, code)
    if listing.status in (Listing.Status.LIVE, Listing.Status.EXPIRED):
        listing.renew()
        messages.success(request, f"آگهی «{listing.title}» برای {to_fa_digits(settings.LISTING_TTL_DAYS)} روز دیگر تمدید شد.")
    return redirect(reverse("accounts:profile") + "#t-active")


@login_required
@require_POST
def delete(request, code):
    listing = _owned(request, code)
    listing.status = Listing.Status.REMOVED
    listing.save()
    messages.success(request, f"آگهی «{listing.title}» حذف شد.")
    return redirect(reverse("accounts:profile"))


# ---------------------------------------------------------------- post / edit
def _categories_json():
    roots = Category.objects.filter(parent__isnull=True).order_by("order").prefetch_related("children")
    data = []
    for r in roots:
        data.append(
            {
                "id": r.id,
                "name": r.name,
                "emoji": r.emoji,
                "children": [{"id": c.id, "name": c.name} for c in r.children.order_by("order")],
            }
        )
    return data


def _districts_json():
    out = {}
    for d in District.objects.filter(is_active=True, city__is_active=True).order_by("order"):
        out.setdefault(str(d.city_id), []).append({"id": d.id, "name": d.name})
    return out


def _save_images(listing, files, start_order=0):
    errors = []
    for i, f in enumerate(files):
        try:
            variants, (w, h) = process_upload(f)
        except InvalidImage as e:
            errors.append(str(e))
            continue
        img = ListingImage(listing=listing, order=start_order + i, width=w, height=h)
        base = f"{listing.code}-{start_order + i}"
        img.image.save(f"{base}.webp", variants["gallery"], save=False)
        img.thumb.save(f"{base}-t.webp", variants["thumb"], save=False)
        img.save()
    return errors


def _form_context(request, form, listing=None, image_error=None, first_error_step=1):
    active_city = City.objects.filter(is_active=True).order_by("order").first()
    return {
        "form": form,
        "listing": listing,
        "types": Listing.Type.choices,
        "enabled_types": [t.value for t in Listing.ENABLED_TYPES],
        "categories_json": json.dumps(_categories_json(), ensure_ascii=False),
        "districts_json": json.dumps(_districts_json(), ensure_ascii=False),
        "ages": AgeRange.choices,
        "brands": Brand.objects.order_by("order"),
        "conditions": Listing.Condition.choices,
        "cities": City.objects.order_by("order"),
        "default_city_id": (listing.city_id if listing else (request.user.city_id or (active_city.id if active_city else None))),
        "default_district_id": (listing.district_id if listing else request.user.district_id),
        "image_error": image_error,
        "first_error_step": first_error_step,
        "existing_images": list(listing.images.all()) if listing else [],
        "max_images": settings.LISTING_MAX_IMAGES,
        "sla": settings.MODERATION_SLA_HOURS,
        "type_meta": {
            "sell": ("🏷️", "قیمت می‌گذارید و می‌فروشید"),
            "free": ("🎁", "می‌بخشید"),
            "donate": ("💚", "مهدکودک یا خیریه"),
            "wanted": ("🔍", "درخواست خرید"),
            "swap": ("🔄", "با اسباب‌بازی دیگر"),
            "rent": ("⏳", "بدون دخالت پلتفرم"),
        },
    }


STEP_OF_FIELD = {
    "type": 1,
    "category": 2,
    "title": 3, "age_range": 3, "brand": 3, "condition": 3, "hygiene_note": 3, "description": 3,
    "is_complete": 3, "has_box": 3, "has_manual": 3, "has_battery": 3, "missing_parts": 3,
    "images": 4,
    "price": 5, "original_price": 5, "is_negotiable": 5, "city": 5, "district": 5, "meetup_hint": 5,
    "allow_chat": 5, "allow_phone": 5, "attested_safe": 5,
}


def _first_error_step(form, image_error):
    steps = [STEP_OF_FIELD.get(f, 3) for f in form.errors]
    if image_error:
        steps.append(4)
    return min(steps) if steps else 1


@login_required
def post(request):
    user = request.user
    if user.is_banned:
        messages.error(request, "حساب شما مسدود شده است و امکان ثبت آگهی ندارد.")
        return redirect("accounts:profile")
    if not user.can_post():
        messages.warning(
            request,
            f"سقف آگهی فعال برای حساب شما <b class='num'>{to_fa_digits(user.listing_cap)}</b> آگهی است. "
            "برای ثبت آگهی تازه یکی از آگهی‌های فعل را فروخته‌شده یا حذف کنید.",
        )
        return redirect("accounts:profile")

    if request.method == "POST":
        form = ListingForm(request.POST)
        files = request.FILES.getlist("images")
        image_error = validate_images(files)
        if form.is_valid() and not image_error:
            listing = form.save(commit=False)
            listing.owner = user
            listing.type = Listing.Type.SELL
            listing.status = Listing.Status.DRAFT
            listing.save()
            errs = _save_images(listing, files)
            if errs or listing.images.count() == 0:
                listing.delete()
                image_error = " ".join(errs) or "عکس‌ها ذخیره نشدند."
            else:
                services.submit_listing(listing)
                if listing.is_live:
                    messages.success(request, f"<b>آگهی «{listing.title}» ثبت و منتشر شد.</b> بررسی خودکار مشکلی پیدا نکرد.")
                else:
                    messages.success(
                        request,
                        f"<b>آگهی «{listing.title}» ثبت شد.</b> در صف بررسی است و تا حداکثر "
                        f"{to_fa_digits(settings.MODERATION_SLA_HOURS)} ساعت دیگر منتشر می‌شود. نتیجه را پیامک می‌کنیم.",
                    )
                return redirect(reverse("accounts:profile") + ("#t-active" if listing.is_live else "#t-pending"))
        ctx = _form_context(request, form, None, image_error, _first_error_step(form, image_error))
        return render(request, "listings/post.html", ctx)

    initial = {"city": user.city_id, "district": user.district_id, "is_complete": True, "is_negotiable": True,
               "allow_chat": True, "allow_phone": True}
    form = ListingForm(initial=initial)
    return render(request, "listings/post.html", _form_context(request, form))


REVIEW_FIELDS = ("title", "description", "price", "category_id", "hygiene_note", "condition")


@login_required
def edit(request, code):
    listing = _owned(request, code)
    if listing.status in (Listing.Status.REMOVED, Listing.Status.SOLD):
        messages.error(request, "این آگهی قابل ویرایش نیست.")
        return redirect("accounts:profile")
    if request.method == "POST":
        before = {f: getattr(listing, f) for f in REVIEW_FIELDS}
        was_status = listing.status
        form = ListingForm(request.POST, instance=listing)
        files = request.FILES.getlist("images")
        image_error = validate_images(files, existing_count=listing.images.count())
        if form.is_valid() and not image_error:
            listing = form.save()
            errs = _save_images(listing, files, start_order=listing.images.count())
            if errs:
                messages.warning(request, " ".join(errs))
            changed = any(before[f] != getattr(listing, f) for f in REVIEW_FIELDS)
            if was_status == Listing.Status.REJECTED or (was_status == Listing.Status.LIVE and changed) or was_status == Listing.Status.DRAFT:
                services.submit_listing(listing)
                if listing.is_live:
                    messages.success(request, f"آگهی «{listing.title}» ویرایش و منتشر شد.")
                else:
                    messages.success(request, f"آگهی «{listing.title}» ویرایش شد و دوباره برای بررسی فرستاده شد.")
            else:
                messages.success(request, f"آگهی «{listing.title}» ذخیره شد.")
            return redirect(reverse("accounts:profile") + ("#t-active" if listing.is_live else "#t-pending"))
        ctx = _form_context(request, form, listing, image_error, _first_error_step(form, image_error))
        return render(request, "listings/post.html", ctx)
    form = ListingForm(instance=listing, initial={"price": listing.price, "original_price": listing.original_price or "",
                                                  "attested_safe": listing.attested_safe})
    return render(request, "listings/post.html", _form_context(request, form, listing))


@login_required
@require_POST
def upload_image(request):
    listing = _owned(request, request.POST.get("code", ""))
    files = request.FILES.getlist("images") or request.FILES.getlist("image")
    err = validate_images(files, existing_count=listing.images.count())
    if err:
        return HttpResponse(f'<div class="hint" style="color:var(--red-600)">{err}</div>', status=400)
    errs = _save_images(listing, files, start_order=listing.images.count())
    html = "".join(
        render_to_string("listings/_upload_slot.html", {"img": im, "listing": listing, "is_cover": i == 0}, request)
        for i, im in enumerate(listing.images.all())
    )
    if errs:
        html += f'<div class="hint" style="color:var(--red-600)">{" ".join(errs)}</div>'
    return HttpResponse(html)


@login_required
@require_POST
def delete_image(request, pk):
    img = get_object_or_404(ListingImage, pk=pk)
    if img.listing.owner != request.user and not request.user.is_staff:
        return HttpResponseForbidden()
    if img.listing.images.count() <= 1:
        return HttpResponse('<div class="hint" style="color:var(--red-600)">آگهی باید حداقل یک عکس داشته باشد.</div>', status=400)
    img.image.delete(save=False)
    img.thumb.delete(save=False)
    img.delete()
    return HttpResponse("")


# ---------------------------------------------------------------- static pages
def page(request, slug):
    if slug not in STATIC_PAGES:
        raise Http404
    return render(request, f"listings/pages/{slug}.html", {"page_title": STATIC_PAGES[slug]})
