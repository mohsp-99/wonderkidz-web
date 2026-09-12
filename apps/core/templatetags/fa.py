from django import template
from django.utils.safestring import mark_safe

from apps.core import dates, text

register = template.Library()


@register.filter(name="fa")
def fa(value):
    return text.to_fa_digits(value)


@register.filter(name="price")
def price(value):
    return text.format_price(value)


@register.filter(name="phone")
def phone(value):
    return text.mask_phone(value)


@register.filter(name="ago")
def ago(value):
    return dates.ago(value)


@register.filter(name="jalali")
def jalali(value, fmt="%d %B %Y"):
    return dates.jalali(value, fmt)


@register.filter(name="jmonth")
def jmonth(value):
    return dates.jalali_month_year(value)


@register.filter(name="hm")
def hm(value):
    return dates.time_hm(value)


@register.filter(name="chat_time")
def chat_time(value):
    return dates.chat_time(value)


@register.filter(name="days_left")
def days_left_filter(value):
    return dates.days_left(value)


@register.simple_tag
def jalali_year():
    return dates.jalali_year()


@register.filter(name="pct_off")
def pct_off(listing):
    p = listing.percent_off
    return text.to_fa_digits(p) if p else ""


@register.filter
def get_item(d, key):
    try:
        return d.get(key)
    except AttributeError:
        return None


@register.filter
def add_str(a, b):
    return f"{a}{b}"


@register.simple_tag(takes_context=True)
def qs_replace(context, **kwargs):
    """Build a querystring from the current request with some params replaced/removed."""
    request = context["request"]
    q = request.GET.copy()
    for k, v in kwargs.items():
        if v is None or v == "":
            q.pop(k, None)
        else:
            q[k] = v
    q.pop("page", None)
    enc = q.urlencode()
    return mark_safe("?" + enc if enc else "?")


@register.simple_tag(takes_context=True)
def qs_toggle(context, key, value):
    """Toggle a value inside a multi-valued querystring param."""
    request = context["request"]
    q = request.GET.copy()
    values = q.getlist(key)
    value = str(value)
    if value in values:
        values.remove(value)
    else:
        values.append(value)
    q.setlist(key, values)
    q.pop("page", None)
    enc = q.urlencode()
    return mark_safe("?" + enc if enc else "?")


@register.filter
def in_list(value, lst):
    return str(value) in [str(x) for x in lst]
