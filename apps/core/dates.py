"""Jalali dates and Persian relative-time strings."""
from datetime import timedelta

import jdatetime
from django.utils import timezone

from .text import to_fa_digits

JALALI_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]
WEEKDAYS = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]


def _local(dt):
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return dt


def jalali(dt, fmt="%d %B %Y"):
    if not dt:
        return ""
    dt = _local(dt)
    j = jdatetime.datetime.fromgregorian(datetime=dt)
    out = fmt.replace("%B", JALALI_MONTHS[j.month - 1]).replace("%A", WEEKDAYS[j.weekday()])
    out = j.strftime(out)
    return to_fa_digits(out)


def jalali_month_year(dt):
    """'مهر ۱۴۰۴' — used for 'member since'."""
    if not dt:
        return ""
    j = jdatetime.datetime.fromgregorian(datetime=_local(dt))
    return f"{JALALI_MONTHS[j.month - 1]} {to_fa_digits(j.year)}"


def jalali_year(dt=None):
    dt = dt or timezone.now()
    return to_fa_digits(jdatetime.datetime.fromgregorian(datetime=_local(dt)).year)


def time_hm(dt):
    return to_fa_digits(_local(dt).strftime("%H:%M"))


def ago(dt) -> str:
    """Divar-style relative time: 'هم‌اکنون', '۲ ساعت پیش', 'دیروز', '۳ روز پیش', then a Jalali date."""
    if not dt:
        return ""
    now = timezone.now()
    delta = now - dt
    s = int(delta.total_seconds())
    if s < 60:
        return "هم‌اکنون"
    if s < 3600:
        return f"{to_fa_digits(s // 60)} دقیقه پیش"
    if s < 86400:
        return f"{to_fa_digits(s // 3600)} ساعت پیش"
    days = s // 86400
    if days == 1:
        return "دیروز"
    if days < 14:
        return f"{to_fa_digits(days)} روز پیش"
    if days < 60:
        return f"{to_fa_digits(days // 7)} هفته پیش"
    return jalali(dt, "%d %B")


def chat_time(dt) -> str:
    """Inbox-style timestamp: HH:MM today, 'دیروز', else 'N روز پیش' / date."""
    if not dt:
        return ""
    local = _local(dt)
    today = _local(timezone.now()).date()
    if local.date() == today:
        return time_hm(dt)
    if local.date() == today - timedelta(days=1):
        return "دیروز"
    return ago(dt)


def days_left(dt) -> int:
    if not dt:
        return 0
    return max(0, (dt - timezone.now()).days)
