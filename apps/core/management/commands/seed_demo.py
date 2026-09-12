"""
Seed the database with the demo content from the planning mockups.

    manage.py seed_demo            # idempotent: creates what is missing
    manage.py seed_demo --flush    # wipe listings/chat/reports/non-superuser users first
"""
import os
import random
from datetime import timedelta
from io import BytesIO

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from apps.accounts.models import SavedSearch, User
from apps.catalog.models import Brand, Category, City, District
from apps.chat.models import Conversation, Message
from apps.core.images import process_upload
from apps.listings.models import Listing, ListingImage, PhoneReveal, Report, SavedListing
from apps.payments.models import Plan

# --------------------------------------------------------------------------- reference data

CITIES = [("تهران", "tehran", True), ("کرج", "karaj", False), ("اصفهان", "isfahan", False)]
DISTRICTS = [("سعادت‌آباد", "saadat-abad"), ("شهرک غرب", "shahrak-gharb"), ("پونک", "punak")]

LEGO_TIPS = """📍|جای عمومی قرار بگذارید. پارک، کافه یا لابی ساختمان. به خانهٔ فروشنده یا خریدار نروید.
💳|هیچ مبلغی از قبل واریز نکنید. نه بیعانه، نه «کارت به کارت برای رزرو». پول را موقع تحویل و بعد از دیدن کالا بدهید.
🔎|کالا را همان‌جا وارسی کنید. تعداد قطعات، ترک‌خوردگی، بوی نم و سلامت قطعات کوچک را ببینید.
🧒|قطعات کوچک برای زیر ۳ سال خطر خفگی دارند. ردهٔ سنی روی جعبه را جدی بگیرید.
🧼|قبل از دادن به کودک بشویید. حتی وقتی فروشنده نوشته شسته شده.
🔋|اسباب‌بازی باتری‌دکمه‌ای را چک کنید که درِ باتری پیچ‌دار و محکم باشد."""

COMMON_TIPS = """📍|جای عمومی قرار بگذارید. پارک، کافه یا لابی ساختمان. به خانهٔ فروشنده یا خریدار نروید.
💳|هیچ مبلغی از قبل واریز نکنید. پول را موقع تحویل و بعد از دیدن کالا بدهید.
🧼|قبل از دادن به کودک بشویید یا ضدعفونی کنید، حتی وقتی فروشنده نوشته تمیز شده."""

CATEGORIES = [
    # name, slug, emoji, color, ph_class, tips, children
    ("عروسک و فیگور", "dolls", "🧸", "var(--amber-100)", "ph-h",
     COMMON_TIPS + "\n🧵|درز دوخت و چشم‌های عروسک را چک کنید که محکم باشند و قطعهٔ کوچک کنده نشود.",
     [("عروسک پارچه‌ای", "plush"), ("فیگور و شخصیت", "figures"), ("عروسک باربی و لباس", "fashion-dolls")]),
    ("لگو و ساختنی", "building", "🧱", "var(--blue-100)", "ph-c", LEGO_TIPS,
     [("لگو و بلوک", "lego-blocks"), ("مگنت و ساخت‌وساز", "magnetic"), ("پازل و چیدنی", "puzzles"), ("ساختنی چوبی", "wooden-building")]),
    ("بازی فکری", "board-games", "🎲", "var(--teal-100)", "ph-e",
     COMMON_TIPS + "\n🃏|کارت‌ها و مهره‌ها را بشمارید؛ بازی ناقص عملاً قابل استفاده نیست.",
     [("بازی رومیزی", "tabletop"), ("کارتی", "card-games"), ("مهارتی و دقت", "dexterity")]),
    ("اسباب‌بازی آموزشی", "educational", "🔤", "var(--green-100)", "ph-d",
     COMMON_TIPS + "\n🔋|اسباب‌بازی باتری‌دار را روشن کنید و درِ باتری را چک کنید که پیچ‌دار باشد.",
     [("حروف و اعداد", "letters-numbers"), ("موزیکال", "musical"), ("علمی", "science")]),
    ("وسایل بازی حیاط", "outdoor", "🛝", "#e6f0d9", "ph-e",
     COMMON_TIPS + "\n🔩|پیچ‌ها، اتصالات و ترک‌خوردگی پلاستیک را با دقت ببینید؛ وسیلهٔ بزرگ باید پایدار باشد.",
     [("تاب و سرسره", "swings-slides"), ("استخر و آب‌بازی", "water-play"), ("چادر و خانهٔ بازی", "play-tents")]),
    ("کتاب کودک", "books", "📚", "var(--violet-100)", "ph-h",
     COMMON_TIPS + "\n📖|صفحات را ورق بزنید؛ پارگی یا خط‌خوردگی را همان‌جا ببینید.",
     [("داستان", "story"), ("آموزشی و مصور", "picture-books"), ("کتاب پارچه‌ای و حمام", "cloth-books")]),
    ("سه‌چرخه و رکابی", "ride-ons", "🚲", "var(--red-100)", "ph-f",
     COMMON_TIPS + "\n🛞|چرخ‌ها، ترمز و لقی فرمان را امتحان کنید؛ کودک باید بتواند پا به زمین برساند.",
     [("سه‌چرخه", "tricycles"), ("اسکوتر", "scooters"), ("دوچرخهٔ کودک", "kids-bikes")]),
    ("ماشین و کنترلی", "vehicles", "🚗", "#e0e8fa", "ph-b",
     COMMON_TIPS + "\n🎮|ریموت و باتری را همان‌جا امتحان کنید؛ ماشین بدون ریموت کاربردی ندارد.",
     [("ماشین شارژی", "ride-on-cars"), ("کنترلی", "rc"), ("ماشین و قطار کوچک", "small-vehicles")]),
    ("هنر و سرگرمی", "arts-crafts", "🎨", "#f6e2ee", "ph-a",
     COMMON_TIPS + "\n🖍️|رنگ‌ها و چسب‌ها تاریخ انقضا دارند؛ بسته‌بندی باز را چک کنید.",
     [("نقاشی و رنگ‌آمیزی", "painting"), ("خمیر و شن بازی", "dough-sand"), ("کاردستی", "crafts")]),
    ("وسایل نوزاد", "baby", "🍼", "var(--amber-100)", "ph-d",
     COMMON_TIPS + "\n🧷|برای زیر ۱ سال هیچ قطعهٔ کوچک یا بند بلندی نباید داشته باشد.",
     [("جغجغه و آویز", "rattles"), ("دندان‌گیر", "teethers"), ("تشک و ژیمناستیک بازی", "play-gyms")]),
]

BRANDS = ["LEGO", "Fisher-Price", "BRIO", "Janod", "PicassoTiles", "VTech", "Viga", "بدون برند / دست‌ساز"]

USERS = [
    # phone, display_name, district slug, joined months ago
    ("09123456789", "مریم ر.", "saadat-abad", 11),
    ("09121111111", "سارا م.", "saadat-abad", 6),
    ("09122222222", "حمید ص.", "punak", 8),
    ("09123333333", "نگار ت.", "shahrak-gharb", 5),
    ("09124444444", "علی م.", "shahrak-gharb", 4),
]

H = timedelta(hours=1)
D = timedelta(days=1)

# (key, title, category slug, brand, age, condition, price, orig, district, owner phone, status, published delta, micro, imgs, description, extra)
LISTINGS = [
    ("lego500", "لگو کلاسیک ۵۰۰ قطعه با جعبهٔ اصلی", "lego-blocks", "LEGO", "5-8", "likenew", 1250000, 3400000, "saadat-abad", "official", "live", 2 * H, 4,
     "ست لگو کلاسیک ۵۰۰ قطعه که حدود شش ماه دست پسرم بوده و حالا سراغ ست‌های بزرگ‌تر رفته. همهٔ قطعات را یکی‌یکی شمرده‌ام و کامل است؛ هیچ قطعه‌ای گم یا شکسته نشده.\n\nجعبهٔ اصلی و دفترچهٔ راهنما هم هست، فقط گوشهٔ جعبه کمی خط افتاده که در عکس دوم مشخص است. قبل از گذاشتن آگهی همه را شسته و خشک کرده‌ام.\n\nبرای بچه‌های بالای ۵ سال عالی است. اگر سؤالی دارید در چت بپرسید؛ تحویل حضوری در سعادت‌آباد.",
     {"has_box": True, "has_manual": True, "hygiene_note": "همهٔ قطعات با آب ولرم و مایع ظرف‌شویی کودک شسته و کاملاً خشک شده‌اند.", "meetup_hint": "میدان کاج، جلوی کتاب‌فروشی", "attributes": {"series": "Classic", "battery": "ندارد"}, "views_count": 147, "reveals_count": 9}),
    ("rattle", "جغجغه و آویز تخت فیشرپرایس", "rattles", "Fisher-Price", "0-1", "new", 180000, 420000, "shahrak-gharb", "09123333333", "live", 5 * H, 3,
     "جغجغه و آویز تخت فیشرپرایس، نو و در جعبه. کادو گرفته بودیم و دو تا داشتیم. پلمب باز نشده.",
     {"has_box": True, "hygiene_note": "نو و استفاده‌نشده، در جعبهٔ پلمب.", "views_count": 62}),
    ("trike", "سه‌چرخهٔ قرمز کودک با دستهٔ راهنما", "tricycles", "بدون برند / دست‌ساز", "1-3", "used", 450000, 1300000, "punak", "09123456789", "live", 3 * D, 5,
     "سه‌چرخهٔ قرمز با دستهٔ راهنمای والد و سایبان. زین قابل تنظیم. دخترم از ۱.۵ سالگی سوارش می‌شد و حالا بزرگ شده. فقط رنگ دستهٔ راهنما کمی رفته که در عکس سوم معلوم است. چرخ‌ها سالم و بدون لقی.",
     {"hygiene_note": "با دستمال و اسپری ضدعفونی تمیز شده.", "meetup_hint": "پارک پونک، ورودی اصلی", "views_count": 89, "reveals_count": 2}),
    ("puzzle", "پازل چوبی حروف الفبای فارسی", "puzzles", "Viga", "3-5", "likenew", 120000, 280000, "saadat-abad", "09123456789", "live", 8 * H, 2,
     "پازل چوبی حروف الفبای فارسی، ۳۲ قطعه کامل. رنگ‌ها سالم، بدون خط‌خوردگی. برای آموزش حروف قبل از مدرسه عالی است.",
     {"hygiene_note": "با دستمال مرطوب بدون الکل تمیز شده.", "views_count": 41}),
    ("rcar", "ماشین شارژی برقی کودک، تک‌سرنشین", "ride-on-cars", "بدون برند / دست‌ساز", "3-5", "used", 4800000, 9500000, "shahrak-gharb", "09124444444", "live", 3 * H, 6,
     "ماشین شارژی کودک، دو سال استفاده شده، باتری سالم و شارژر همراهشه. ریموت کنترل والد هم داره. بچه‌ام بزرگ شده و دیگه سوارش نمی‌شه.",
     {"has_battery": True, "hygiene_note": "با دستمال مرطوب تمیز شده.", "attributes": {"battery": "۱۲ ولت، شارژر همراه"}, "views_count": 120, "reveals_count": 4}),
    ("teddy", "عروسک خرس تدی پارچه‌ای بزرگ", "plush", "بدون برند / دست‌ساز", "1-3", "likenew", 95000, 300000, "punak", "09122222222", "live", 1 * D, 2,
     "خرس تدی ۶۰ سانتی، پارچه‌ای و نرم. قابل شست‌وشو در ماشین لباسشویی. یک لک کوچک روی پا داشت که با شستن رفت.",
     {"hygiene_note": "در ماشین لباسشویی با شویندهٔ کودک شسته شده.", "attributes": {"washable": True}, "views_count": 55}),
    ("jenga", "بازی فکری جنگا چوبی ۵۴ قطعه", "dexterity", "بدون برند / دست‌ساز", "5-8", "new", 165000, 260000, "saadat-abad", "09123456789", "live", 6 * H, 3,
     "جنگا چوبی ۵۴ قطعه، پلمب و استفاده‌نشده. دو تا کادو گرفته بودیم.",
     {"has_box": True, "hygiene_note": "نو و پلمب.", "views_count": 62}),
    ("brio", "ریل و قطار چوبی برایو ۴۰ قطعه", "wooden-building", "BRIO", "3-5", "likenew", 850000, 2600000, "shahrak-gharb", "official", "live", 4 * H, 5,
     "ست ریل و قطار چوبی برایو ۴۰ قطعه، شامل پل، تونل و دو واگن مغناطیسی. همهٔ قطعات شمرده شده و کامل است.",
     {"has_box": True, "hygiene_note": "قطعات چوبی با دستمال نم‌دار تمیز و خشک شده‌اند.", "views_count": 98, "reveals_count": 3}),
    ("paint", "ست نقاشی و آبرنگ کودک، ۴۶ قلم", "painting", "بدون برند / دست‌ساز", "3-5", "new", 140000, 220000, "punak", "09121111111", "live", 2 * D, 2,
     "ست نقاشی ۴۶ قلم شامل آبرنگ، مداد رنگی، ماژیک و قلم‌مو. نو، فقط جعبه‌اش باز شده.",
     {"has_box": True, "hygiene_note": "نو و استفاده‌نشده.", "allow_chat": False, "views_count": 30}),
    ("slide", "تاب و سرسرهٔ پلاستیکی حیاط", "swings-slides", "بدون برند / دست‌ساز", "1-3", "used", 2900000, 6800000, "saadat-abad", "09122222222", "live", 10 * H, 4,
     "تاب و سرسرهٔ پلاستیکی حیاط، سه سال در حیاط بوده. رنگ کمی آفتاب‌خورده ولی سالم و پایدار. همهٔ پیچ‌ها کامل. حمل با وانت به عهدهٔ خریدار.",
     {"hygiene_note": "با آب و شویندهٔ ملایم شسته شده.", "meetup_hint": "درب منزل، با هماهنگی قبلی", "views_count": 77}),
    ("books10", "مجموعهٔ ۱۰ جلدی کتاب داستان کودک", "story", "بدون برند / دست‌ساز", "3-5", "likenew", 220000, 650000, "shahrak-gharb", "09123456789", "sold", 3 * D, 3,
     "مجموعهٔ ده جلدی داستان‌های کودکانه با تصاویر رنگی. هر ده جلد سالم، فقط جلد اول کمی تا خورده.",
     {"hygiene_note": "تمیز و بدون بو.", "views_count": 66}),
    ("picasso", "مگنت ساختنی پیکاسوتایلز ۶۰ قطعه", "magnetic", "PicassoTiles", "3-5", "likenew", 1650000, 4200000, "punak", "official", "live", 7 * H, 4,
     "مگنت ساختنی پیکاسوتایلز ۶۰ قطعه، اورجینال. آهن‌رباها همه قوی و سالم. جعبهٔ اصلی موجود.",
     {"has_box": True, "hygiene_note": "قطعات با دستمال و اسپری ضدعفونی تمیز شده‌اند.", "views_count": 110, "reveals_count": 5}),
    ("scooter", "اسکوتر سه‌چرخ کودک چراغ‌دار", "scooters", "بدون برند / دست‌ساز", "5-8", "used", 680000, 1900000, "saadat-abad", "09121111111", "live", 3 * D, 3,
     "اسکوتر سه‌چرخ با چرخ‌های چراغ‌دار و ارتفاع قابل تنظیم. یک سال استفاده شده، ترمز عقب سالم.",
     {"hygiene_note": "با دستمال مرطوب تمیز شده.", "views_count": 48}),
    ("vtech", "میز فعالیت آموزشی وی‌تک (موزیکال)", "musical", "VTech", "1-3", "repair", 520000, 2400000, "punak", "09123456789", "live", 4 * D, 2,
     "میز فعالیت وی‌تک با پیانو و صفحهٔ چرخان. یکی از دکمه‌ها گیر می‌کند و بدون باتری تحویل می‌دهم. بقیهٔ قسمت‌ها سالم.",
     {"hygiene_note": "با دستمال مرطوب تمیز شده.", "attributes": {"battery": "بدون باتری"}, "expires_in_days": 11, "views_count": 12}),
    # ---- more live listings to fill the board
    ("duplo", "لگو دوپلو مزرعه ۴۵ قطعه", "lego-blocks", "LEGO", "1-3", "used", 690000, 1900000, "shahrak-gharb", "09121111111", "live", 12 * H, 3,
     "لگو دوپلو ست مزرعه با حیوانات و تراکتور. دو قطعهٔ حصار کم دارد که در توضیحات نوشتم. بقیه کامل.",
     {"is_complete": False, "missing_parts": True, "hygiene_note": "قطعات با آب ولرم شسته شده.", "views_count": 35}),
    ("janod-stack", "حلقه‌های رنگی چوبی ژانود", "wooden-building", "Janod", "0-1", "likenew", 210000, 520000, "saadat-abad", "09123333333", "live", 1 * D, 2,
     "برج حلقه‌های رنگی چوبی ژانود، رنگ‌ها سالم و بدون ترک.",
     {"hygiene_note": "با دستمال نم‌دار تمیز شده.", "views_count": 22}),
    ("barbie", "عروسک باربی با سه دست لباس", "fashion-dolls", "بدون برند / دست‌ساز", "5-8", "used", 260000, 700000, "punak", "09121111111", "live", 15 * H, 3,
     "عروسک باربی اورجینال با سه دست لباس و کفش. موها مرتب و سالم.",
     {"hygiene_note": "لباس‌ها شسته و عروسک با دستمال تمیز شده.", "views_count": 40}),
    ("monopoly", "بازی رومیزی مونوپولی نسخهٔ کودک", "tabletop", "بدون برند / دست‌ساز", "5-8", "likenew", 310000, 690000, "shahrak-gharb", "09122222222", "live", 20 * H, 2,
     "مونوپولی جونیور، دو بار بازی شده. همهٔ کارت‌ها و مهره‌ها شمرده و کامل.",
     {"has_box": True, "has_manual": True, "hygiene_note": "تمیز و بدون استفادهٔ زیاد.", "views_count": 28}),
    ("uno", "کارت بازی اونو اورجینال", "card-games", "بدون برند / دست‌ساز", "8+", "used", 60000, 150000, "saadat-abad", "09124444444", "live", 2 * D, 2,
     "کارت اونو اورجینال، ۱۰۸ کارت کامل. گوشهٔ چند کارت کمی نرم شده.",
     {"has_box": True, "hygiene_note": "کارت‌ها با دستمال الکلی تمیز شده‌اند.", "views_count": 19}),
    ("abc-board", "تختهٔ حروف مغناطیسی انگلیسی", "letters-numbers", "بدون برند / دست‌ساز", "3-5", "likenew", 130000, 320000, "punak", "09123333333", "live", 9 * H, 2,
     "تختهٔ مغناطیسی با حروف بزرگ و کوچک انگلیسی و اعداد. کامل.",
     {"hygiene_note": "با دستمال مرطوب تمیز شده.", "views_count": 17}),
    ("micro", "میکروسکوپ آموزشی کودک با ۱۲ اسلاید", "science", "بدون برند / دست‌ساز", "8+", "used", 480000, 1200000, "shahrak-gharb", "09122222222", "live", 5 * D, 3,
     "میکروسکوپ آموزشی با بزرگنمایی ۱۰۰ تا ۴۰۰، ۱۲ اسلاید آماده. چراغ با باتری کار می‌کند.",
     {"has_box": True, "has_battery": True, "hygiene_note": "تمیز شده.", "views_count": 33}),
    ("pool", "استخر بادی سه‌طبقه اینتکس", "water-play", "بدون برند / دست‌ساز", "1-3", "used", 350000, 900000, "saadat-abad", "09121111111", "live", 6 * D, 2,
     "استخر بادی سه‌طبقه، یک تابستان استفاده شده. بدون سوراخ، تست شده.",
     {"hygiene_note": "شسته و کاملاً خشک شده.", "views_count": 26}),
    ("tent", "چادر بازی کودک با تونل", "play-tents", "بدون برند / دست‌ساز", "3-5", "likenew", 290000, 750000, "punak", "09123456789", "live", 30 * H, 3,
     "چادر بازی با تونل اتصالی و توپ‌های رنگی (حدود ۵۰ توپ). تا می‌شود و جای کمی می‌گیرد.",
     {"hygiene_note": "پارچه شسته و توپ‌ها ضدعفونی شده‌اند.", "views_count": 44}),
    ("cloth-book", "کتاب پارچه‌ای نوزاد با آینه", "cloth-books", "بدون برند / دست‌ساز", "0-1", "likenew", 70000, 180000, "shahrak-gharb", "09123333333", "live", 11 * H, 2,
     "کتاب پارچه‌ای نرم با آینه و صداهای خش‌خش. قابل شست‌وشو.",
     {"hygiene_note": "در ماشین لباسشویی شسته شده.", "views_count": 15}),
    ("picture-books", "۵ جلد کتاب مصور آموزش رنگ‌ها و اشکال", "picture-books", "بدون برند / دست‌ساز", "1-3", "used", 110000, 300000, "saadat-abad", "09124444444", "live", 4 * D, 2,
     "پنج جلد کتاب مقوایی مصور. گوشهٔ چند صفحه کمی خورده شده ولی همه خوانا.",
     {"hygiene_note": "با دستمال تمیز شده.", "views_count": 21}),
    ("bike", "دوچرخهٔ ۱۶ کودک با کمکی", "kids-bikes", "بدون برند / دست‌ساز", "5-8", "used", 1900000, 4500000, "punak", "09122222222", "live", 2 * D, 4,
     "دوچرخهٔ سایز ۱۶ با چرخ کمکی و زنگ. ترمزها تنظیم شده، لاستیک‌ها سالم.",
     {"hygiene_note": "شسته شده.", "meetup_hint": "پارک پونک", "views_count": 58, "reveals_count": 3}),
    ("rc-car", "ماشین کنترلی آفرود با شارژر", "rc", "بدون برند / دست‌ساز", "8+", "used", 720000, 1800000, "shahrak-gharb", "09124444444", "live", 18 * H, 3,
     "ماشین کنترلی آفرود مقیاس ۱:۱۶ با ریموت و شارژر. باتری حدود ۲۰ دقیقه کار می‌کند.",
     {"has_battery": True, "hygiene_note": "تمیز شده.", "views_count": 37}),
    ("hotwheels", "۱۲ ماشین کوچک فلزی هات‌ویلز", "small-vehicles", "بدون برند / دست‌ساز", "3-5", "used", 240000, 600000, "saadat-abad", "09121111111", "live", 7 * D, 2,
     "دوازده ماشین فلزی هات‌ویلز، سالم و بدون شکستگی. رنگ چند تا کمی رفته.",
     {"hygiene_note": "با آب و صابون شسته شده‌اند.", "views_count": 29}),
    ("playdoh", "ست خمیر بازی پلی‌دو با قالب", "dough-sand", "بدون برند / دست‌ساز", "3-5", "new", 190000, 380000, "punak", "09123333333", "live", 26 * H, 2,
     "ست خمیر بازی با ۸ رنگ و قالب‌های حیوانات. خمیرها پلمب.",
     {"has_box": True, "hygiene_note": "نو.", "views_count": 14}),
    ("craft", "ست کاردستی و مهره‌بافی", "crafts", "بدون برند / دست‌ساز", "5-8", "likenew", 85000, 200000, "shahrak-gharb", "09122222222", "live", 3 * D, 2,
     "ست مهره‌بافی با بیش از ۵۰۰ مهرهٔ رنگی و نخ. یک بار استفاده شده.",
     {"hygiene_note": "تمیز.", "views_count": 11}),
    ("teether", "دندان‌گیر سیلیکونی سوفی", "teethers", "بدون برند / دست‌ساز", "0-1", "new", 150000, 350000, "saadat-abad", "09123333333", "live", 13 * H, 2,
     "دندان‌گیر زرافهٔ سوفی، نو و در جعبه.",
     {"has_box": True, "hygiene_note": "نو و پلمب.", "views_count": 24}),
    ("playgym", "تشک بازی و ژیمناستیک فیشرپرایس", "play-gyms", "Fisher-Price", "0-1", "likenew", 640000, 1600000, "punak", "09121111111", "live", 5 * D, 3,
     "تشک بازی فیشرپرایس با آویزهای موزیکال. سه ماه استفاده شده.",
     {"has_battery": True, "hygiene_note": "تشک شسته و آویزها ضدعفونی شده‌اند.", "views_count": 52, "reveals_count": 2}),
    ("figures", "ست ۸ فیگور حیوانات جنگل", "figures", "بدون برند / دست‌ساز", "3-5", "likenew", 175000, 400000, "shahrak-gharb", "09124444444", "live", 2 * D, 2,
     "هشت فیگور حیوانات جنگل با کیفیت، بدون شکستگی.",
     {"hygiene_note": "با آب و صابون شسته شده‌اند.", "views_count": 20}),
    ("lego-city", "لگو سیتی ایستگاه آتش‌نشانی", "lego-blocks", "LEGO", "5-8", "used", 980000, 2900000, "punk", "official", "live", 28 * H, 4,
     "لگو سیتی ایستگاه آتش‌نشانی با دفترچهٔ راهنما. یک مینی‌فیگور کم دارد.",
     {"has_manual": True, "is_complete": False, "missing_parts": True, "hygiene_note": "قطعات شسته و خشک شده‌اند.", "views_count": 71, "reveals_count": 2}),
    ("viga-kitchen", "آشپزخانهٔ چوبی کودک ویگا", "wooden-building", "Viga", "3-5", "used", 2200000, 5800000, "saadat-abad", "official", "live", 40 * H, 5,
     "آشپزخانهٔ چوبی ویگا با لوازم. رنگ سالم، دو تا از لوازم آشپزخانه کم است.",
     {"hygiene_note": "با دستمال و شویندهٔ ملایم تمیز شده.", "meetup_hint": "میدان کاج", "views_count": 83, "reveals_count": 4}),
    # ---- pending / rejected / sold
    ("pend-lego", "لگو کلاسیک ۵۰۰ قطعه با جعبهٔ اصلی", "lego-blocks", "LEGO", "5-8", "likenew", 1250000, 3400000, "saadat-abad", "09123456789", "pending", 8 * timedelta(minutes=1), 4,
     "ست لگو کلاسیک ۵۰۰ قطعه که حدود شش ماه دست پسرم بوده. همهٔ قطعات را شمرده‌ام و کامل است. گوشهٔ جعبه کمی خط افتاده که در عکس دوم مشخص است.",
     {"has_box": True, "has_manual": True, "hygiene_note": "شسته و خشک شده.", "meetup_hint": "میدان کاج، جلوی کتاب‌فروشی"}),
    ("pend-car", "ماشین شارژی برقی کودک، تک‌سرنشین", "ride-on-cars", "بدون برند / دست‌ساز", "3-5", "used", 4800000, 9500000, "shahrak-gharb", "09124444444", "pending", 34 * timedelta(minutes=1), 6,
     "ماشین شارژی کودک، دو سال استفاده شده، باتری سالم و شارژر همراهشه. ریموت کنترل والد هم داره. بچه‌ام بزرگ شده و دیگه سوارش نمی‌شه.",
     {"has_battery": True, "hygiene_note": "با دستمال مرطوب تمیز شده",
      "auto_flags": [{"code": "child_photo", "level": "danger", "text": "در عکس شمارهٔ ۲ احتمالاً چهرهٔ کودک دیده می‌شود (اطمینان ۸۷٪). طبق قانون، عکس کودک مجاز نیست.", "image_index": 2}]}),
    ("pend-slide", "تاب و سرسرهٔ پلاستیکی حیاط", "swings-slides", "بدون برند / دست‌ساز", "1-3", "used", 290000, None, "punak", "09121111111", "pending", 19 * timedelta(minutes=1), 1,
     "تاب و سرسره سالم، فقط پلاستیکش کمی رنگ‌پریده. سریع بفروشم چون جا نداریم.",
     {"hygiene_note": "", "auto_flags": [
         {"code": "price_outlier", "level": "warn", "text": "قیمت بسیار پایین‌تر از میانگین دسته (میانگین ۲٬۶۰۰٬۰۰۰ تومان). الگوی رایج کلاهبرداری «بیعانه بگیر و غیب شو». حساب تازه و فقط یک عکس."},
         {"code": "few_images", "level": "warn", "text": "فقط یک عکس دارد."},
         {"code": "hygiene_empty", "level": "danger", "text": "یادداشت بهداشتی خالی است."}]}),
    ("rej-car", "ماشین شارژی برقی کودک", "ride-on-cars", "بدون برند / دست‌ساز", "3-5", "used", 4200000, 9000000, "saadat-abad", "09123456789", "rejected", 2 * D, 3,
     "ماشین شارژی کودک با ریموت، دو سال استفاده شده.",
     {"has_battery": True, "hygiene_note": "با دستمال مرطوب تمیز شده.", "reject_reason": "در عکس‌ها چهرهٔ کودک دیده می‌شود", "reject_note": "در عکس دوم چهرهٔ کودک دیده می‌شود. عکس را عوض کنید و دوباره برای بررسی بفرستید."}),
    ("sold-teddy", "عروسک خرس تدی پارچه‌ای بزرگ", "plush", "بدون برند / دست‌ساز", "1-3", "likenew", 95000, 300000, "saadat-abad", "09123456789", "sold", 12 * D, 2,
     "خرس تدی پارچه‌ای بزرگ و نرم، قابل شست‌وشو.",
     {"hygiene_note": "شسته شده.", "views_count": 40}),
    ("sold-paint", "ست نقاشی و آبرنگ کودک، ۴۶ قلم", "painting", "بدون برند / دست‌ساز", "3-5", "new", 140000, 220000, "saadat-abad", "09123456789", "sold", 20 * D, 2,
     "ست نقاشی ۴۶ قلم، نو.",
     {"has_box": True, "hygiene_note": "نو.", "views_count": 33}),
]

GRADIENTS = {
    "ph-a": ("#fde8cc", "#f8cfa0"), "ph-b": ("#d7ede9", "#a8d9d0"), "ph-c": ("#e0e8fa", "#b9cdf0"),
    "ph-d": ("#f6e2ee", "#e3bcd6"), "ph-e": ("#e6f0d9", "#c3deae"), "ph-f": ("#fae7e3", "#f2c4bb"),
    "ph-g": ("#eee6f8", "#d0bdec"), "ph-h": ("#fdf3d4", "#f6e09a"),
}
EMOJI_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/truetype/seguiemj.ttf",
]
DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))


def make_placeholder(ph_class, emoji, label, index, count):
    """1200x900 pastel gradient with the category emoji (if a colour-emoji font exists) or a big initial."""
    w, h = 1200, 900
    c1, c2 = (_hex(x) for x in GRADIENTS.get(ph_class, GRADIENTS["ph-a"]))
    # diagonal gradient: build a tiny 2x2 and let bilinear resize interpolate it
    tiny = Image.new("RGB", (2, 2))
    tiny.putdata([c1, tuple((a + b) // 2 for a, b in zip(c1, c2)), tuple((a + b) // 2 for a, b in zip(c1, c2)), c2])
    img = tiny.resize((w, h), Image.BILINEAR)
    draw = ImageDraw.Draw(img)
    emoji_font = None
    for path in EMOJI_FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                emoji_font = ImageFont.truetype(path, 109)  # NotoColorEmoji only renders at 109
                break
            except OSError:
                pass
    if emoji_font is not None:
        try:
            draw.text((w // 2, h // 2), emoji, font=emoji_font, anchor="mm", embedded_color=True)
        except TypeError:
            emoji_font = None
    if emoji_font is None:
        # Fallback: a soft circle with the Latin/first initial of the label.
        r = 170
        draw.ellipse((w // 2 - r, h // 2 - r, w // 2 + r, h // 2 + r), fill=(255, 255, 255))
        try:
            font = ImageFont.truetype(DEJAVU, 180)
        except OSError:
            font = ImageFont.load_default()
        initial = next((ch for ch in label if ch.isalnum()), "W")
        draw.text((w // 2, h // 2 - 8), initial, font=font, fill=(23, 33, 31), anchor="mm")
    try:
        small = ImageFont.truetype(DEJAVU, 34)
    except OSError:
        small = ImageFont.load_default()
    draw.text((w - 40, h - 40), f"{index}/{count}", font=small, fill=(23, 33, 31), anchor="rb")
    # subtle dotted texture like the CSS placeholder
    for y in range(0, h, 28):
        for x in range(0, w, 28):
            draw.ellipse((x, y, x + 3, y + 3), fill=(255, 255, 255))
    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


class Command(BaseCommand):
    help = "Seed demo data mirroring the planning mockups (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Delete listings/chat/reports/non-superuser users first")

    # ------------------------------------------------------------------ helpers
    def flush(self):
        Report.objects.all().delete()
        Message.objects.all().delete()
        Conversation.objects.all().delete()
        for li in ListingImage.objects.all():
            li.image.delete(save=False)
            li.thumb.delete(save=False)
        Listing.objects.all().delete()
        SavedSearch.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        self.stdout.write("flushed listings, chat, reports, users")

    def seed_catalog(self):
        cities = {}
        for i, (name, slug, active) in enumerate(CITIES):
            c, _ = City.objects.update_or_create(slug=slug, defaults={"name": name, "is_active": active, "order": i})
            cities[slug] = c
        districts = {}
        for i, (name, slug) in enumerate(DISTRICTS):
            d, _ = District.objects.update_or_create(
                city=cities["tehran"], slug=slug, defaults={"name": name, "is_active": True, "order": i}
            )
            districts[slug] = d
        cats = {}
        for i, (name, slug, emoji, color, ph, tips, children) in enumerate(CATEGORIES):
            root, _ = Category.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "emoji": emoji, "color": color, "ph_class": ph, "order": i, "safety_tips": tips,
                          "parent": None, "seo_title": f"{name} دست‌دوم کودک", "seo_description": f"خرید و فروش {name} دست‌دوم بین والدین تهران"},
            )
            cats[slug] = root
            for j, (cname, cslug) in enumerate(children):
                ch, _ = Category.objects.update_or_create(
                    slug=cslug, defaults={"name": cname, "parent": root, "emoji": emoji, "color": color, "ph_class": ph, "order": j}
                )
                cats[cslug] = ch
        brands = {}
        for i, name in enumerate(BRANDS):
            slug = {"بدون برند / دست‌ساز": "no-brand"}.get(name, name.lower().replace(" ", "-"))
            b, _ = Brand.objects.update_or_create(slug=slug, defaults={"name": name, "order": i, "is_featured": True})
            brands[name] = b
        return cities, districts, cats, brands

    def seed_users(self, cities, districts):
        now = timezone.now()
        admin, created = User.objects.get_or_create(
            phone="09120000000",
            defaults={"display_name": "سمانه ک.", "is_staff": True, "is_superuser": True, "is_verified": True,
                      "city": cities["tehran"], "district": districts["saadat-abad"]},
        )
        if created or not admin.has_usable_password():
            admin.set_password("admin")
            admin.save()
        official, _ = User.objects.update_or_create(
            phone="09128890878",
            defaults={"display_name": "فروشگاه وندرکیدز", "account_type": User.AccountType.OFFICIAL, "is_verified": True,
                      "city": cities["tehran"], "district": districts["saadat-abad"], "listing_cap": 500,
                      "date_joined": now - timedelta(days=540)},
        )
        users = {"official": official, "admin": admin}
        for phone, name, dslug, months in USERS:
            u, _ = User.objects.update_or_create(
                phone=phone,
                defaults={"display_name": name, "is_verified": True, "city": cities["tehran"], "district": districts[dslug],
                          "date_joined": now - timedelta(days=30 * months)},
            )
            users[phone] = u
        return users

    def add_images(self, listing, count):
        if listing.images.exists():
            return
        for i in range(1, count + 1):
            buf = make_placeholder(listing.ph_class, listing.emoji, listing.title, i, count)
            buf.name = f"{listing.code}-{i}.png"
            buf.size = len(buf.getvalue())
            variants, (w, h) = process_upload(buf)
            li = ListingImage(listing=listing, order=i - 1, width=w, height=h)
            li.image.save(f"{listing.code}-{i}.webp", variants["gallery"], save=False)
            li.thumb.save(f"{listing.code}-{i}-t.webp", variants["thumb"], save=False)
            li.save()

    def seed_listings(self, cities, districts, cats, brands, users):
        now = timezone.now()
        out = {}
        for row in LISTINGS:
            key, title, cslug, brand, age, cond, price, orig, dslug, owner, status, delta, nimg, desc, extra = row
            extra = dict(extra)
            dslug = "punak" if dslug == "punk" else dslug
            owner_user = users[owner]
            expires_in = extra.pop("expires_in_days", None)
            auto_flags = extra.pop("auto_flags", [])
            reject_reason = extra.pop("reject_reason", "")
            reject_note = extra.pop("reject_note", "")
            existing = Listing.objects.filter(owner=owner_user, title=title, status=status).first()
            if existing:
                out[key] = existing
                continue
            listing = Listing(
                owner=owner_user, title=title, category=cats[cslug], brand=brands.get(brand), age_range=age,
                condition=cond, price=price, original_price=orig, city=cities["tehran"], district=districts[dslug],
                description=desc, attested_safe=True, is_negotiable=True, auto_flags=auto_flags,
                reject_reason=reject_reason, reject_note=reject_note, **extra,
            )
            listing.hygiene_note = extra.get("hygiene_note", "")
            if status == "live":
                listing.status = Listing.Status.LIVE
                listing.submitted_at = now - delta - timedelta(minutes=45)
                listing.published_at = now - delta
                listing.expires_at = (now + timedelta(days=expires_in)) if expires_in else listing.published_at + timedelta(days=settings.LISTING_TTL_DAYS)
                listing.reviewed_by = users["admin"]
                listing.reviewed_at = listing.published_at
            elif status == "pending":
                listing.status = Listing.Status.PENDING
                listing.submitted_at = now - delta
            elif status == "rejected":
                listing.status = Listing.Status.REJECTED
                listing.submitted_at = now - delta - timedelta(hours=1)
                listing.reviewed_by = users["admin"]
                listing.reviewed_at = now - delta
            elif status == "sold":
                listing.status = Listing.Status.SOLD
                listing.submitted_at = now - delta - timedelta(days=10)
                listing.published_at = now - delta - timedelta(days=9)
                listing.expires_at = listing.published_at + timedelta(days=settings.LISTING_TTL_DAYS)
                listing.sold_at = now - delta
            listing.save()
            # created_at is auto_now_add; backdate for realism
            Listing.objects.filter(pk=listing.pk).update(created_at=listing.submitted_at or now)
            self.add_images(listing, nimg)
            out[key] = listing
        return out

    def seed_chat(self, users, L):
        now = timezone.now()
        maryam, sara, hamid, negar = users["09123456789"], users["09121111111"], users["09122222222"], users["09123333333"]
        official = users["official"]

        def convo(listing, buyer, seller, msgs, last_delta, closed=False, feedback=""):
            c, created = Conversation.objects.get_or_create(listing=listing, buyer=buyer, defaults={"seller": seller})
            if not created:
                return c
            t = now - last_delta - timedelta(minutes=5 * len(msgs))
            for sender, body, read in msgs:
                m = Message.objects.create(conversation=c, sender=None if sender is None else sender, body=body,
                                           is_system=sender is None, is_read=read)
                t += timedelta(minutes=random.randint(2, 20))
                Message.objects.filter(pk=m.pk).update(created_at=t)
            Conversation.objects.filter(pk=c.pk).update(last_message_at=t, is_closed=closed, buyer_feedback=feedback)
            return c

        # Thread 1: Sara buying the LEGO from the official account (viewed as the seller in the mockup — here maryam owns "pend-lego"; use the live one owned by official)
        c1 = convo(L["lego500"], sara, official, [
            (sara, "سلام وقت بخیر 🌸 لگو هنوز هست؟", True),
            (official, "سلام، بله هست.", True),
            (sara, "قطعاتش واقعاً کامله؟ برای تولد پسرم می‌خوام، نمی‌خوام نصفه باشه.", True),
            (official, "بله، خودم یکی‌یکی شمردم، ۵۰۰ تا کامله. دفترچه و جعبه‌ش هم هست. عکس چهارم همهٔ قطعات کنار همه.", True),
            (sara, "عالیه. شسته شده؟ بچهٔ من هنوز دستشو می‌ذاره دهنش.", True),
            (official, "آره با آب ولرم و مایع ظرف‌شویی کودک شستم و خشک شد. ولی خودتون هم قبل از دادن به بچه یه بار بشورید بهتره 🙂", True),
            (None, "⚠️ اگر طرف مقابل از شما خواست بیعانه یا «هزینهٔ رزرو» کارت‌به‌کارت کنید، معامله را ادامه ندهید و گزارش کنید.", True),
            (sara, "حتماً. ۱٬۱۰۰ می‌شه؟", True),
            (official, "۱٬۲۰۰ بشه قبوله.", True),
            (sara, "قبوله 👌", False),
            (sara, "پس فردا ساعت ۵ میدان کاج خوبه؟", False),
        ], timedelta(minutes=30))
        # Thread 2: Maryam asking Hamid about... the trike is Maryam's; in the mockup Maryam is the buyer of Hamid's trike. Use the teddy (Hamid's) instead? Keep mockup: Hamid sells trike → owner is Maryam here, so flip: Maryam buys Hamid's teddy? Simplest faithful option: Maryam ↔ Hamid on the bike Hamid owns.
        c2 = convo(L["bike"], maryam, hamid, [
            (maryam, "سلام، این دوچرخه برای بچهٔ پنج ساله مناسبه؟", True),
            (hamid, "سلام. بله، زینش قابل تنظیمه. دختر من از ۴.۵ سالگی سوارش می‌شد.", True),
            (maryam, "چرخ جلو لقی نداره؟", True),
            (hamid, "نه، سالمه. فقط رنگ گلگیر یه‌کم رفته که در عکس سوم معلومه.", True),
            (None, "🔓 شمارهٔ تماس فروشنده برای شما نمایش داده شد.", True),
        ], timedelta(days=1))
        # Thread 3: Negar bought Maryam's books (sold)
        c3 = convo(L["books10"], negar, maryam, [
            (negar, "سلام، کتاب‌ها هنوز هست؟", True),
            (maryam, "سلام، بله. هر ده جلد سالمه، فقط جلد اول کمی تا خورده.", True),
            (negar, "عالیه. فردا عصر شهرک غرب می‌تونم بیام.", True),
            (maryam, "ممنون، فروخته شد 🙏", True),
            (None, "این گفت‌وگو بسته شده است، ولی تاریخچه‌اش برای هر دو طرف باقی می‌ماند.", True),
        ], timedelta(days=3), closed=True, feedback="good")
        # a scam-shaped chat on the flagged slide (for the report)
        c4 = convo(L["pend-slide"], negar, sara, [
            (negar, "سلام، تاب و سرسره موجوده؟", True),
            (sara, "سلام بله. چون خیلی‌ها می‌خوان، اگه ۲۰۰ تومن بیعانه کارت‌به‌کارت کنید براتون نگه می‌دارم.", True),
            (negar, "نه ممنون، حضوری می‌بینم و پرداخت می‌کنم.", True),
        ], timedelta(minutes=40))
        return c1, c2, c3, c4

    def seed_reports(self, users, L, convos):
        c1, c2, c3, c4 = convos
        now = timezone.now()
        negar, hamid, ali = users["09123333333"], users["09122222222"], users["09124444444"]
        rows = [
            dict(reporter=negar, listing=L["pend-slide"], reason=Report.Reason.SCAM, priority=Report.Priority.URGENT,
                 note="در چت درخواست بیعانهٔ کارت‌به‌کارت کرد.", created=now - timedelta(minutes=40)),
            dict(reporter=hamid, listing=L["pend-slide"], reason=Report.Reason.SCAM, priority=Report.Priority.URGENT,
                 note="قیمت غیرواقعی و اصرار به بیعانه.", created=now - timedelta(minutes=35)),
            dict(reporter=ali, listing=L["teddy"], reason=Report.Reason.MISMATCH, priority=Report.Priority.NORMAL,
                 note="وضعیت واقعی با آگهی نمی‌خواند (لک روی پارچه).", created=now - timedelta(hours=5)),
            dict(reporter=negar, conversation=c4, reason=Report.Reason.ABUSE, priority=Report.Priority.NORMAL,
                 note="پیام توهین‌آمیز بعد از رد کردن بیعانه.", created=now - timedelta(days=1)),
        ]
        n = 0
        for r in rows:
            created = r.pop("created")
            obj, made = Report.objects.get_or_create(
                reporter=r["reporter"], listing=r.get("listing"), conversation=r.get("conversation"), reason=r["reason"],
                defaults={"note": r["note"], "priority": r["priority"]},
            )
            if made:
                Report.objects.filter(pk=obj.pk).update(created_at=created)
                n += 1
        return n

    def seed_misc(self, users, L):
        maryam, sara, hamid, negar, ali = (users[p] for p in ("09123456789", "09121111111", "09122222222", "09123333333", "09124444444"))
        for u, key in [(sara, "lego500"), (hamid, "lego500"), (maryam, "bike"), (ali, "picasso"), (negar, "trike"), (sara, "brio")]:
            if not PhoneReveal.objects.filter(user=u, listing=L[key]).exists():
                PhoneReveal.objects.create(user=u, listing=L[key])
        for u, key in [(maryam, "brio"), (maryam, "slide"), (maryam, "rattle"), (sara, "trike"), (hamid, "puzzle")]:
            SavedListing.objects.get_or_create(user=u, listing=L[key])
        SavedSearch.objects.get_or_create(
            user=maryam, label="لگو، ۳ تا ۵ سال، سعادت‌آباد",
            defaults={"querystring": "q=لگو&age=3-5&district=saadat-abad"},
        )
        Plan.objects.get_or_create(
            name="نردبان ۷ روزه", kind=Plan.Kind.PROMOTE,
            defaults={"price": 49000, "duration_days": 7, "is_active": False, "description": "آگهی شما هفت روز بالای فهرست دیده می‌شود."},
        )
        Plan.objects.get_or_create(
            name="اشتراک فروشندهٔ حرفه‌ای", kind=Plan.Kind.SUBSCRIPTION,
            defaults={"price": 290000, "duration_days": 30, "is_active": False, "description": "سقف آگهی بیشتر و نشان فروشندهٔ حرفه‌ای."},
        )

    # ------------------------------------------------------------------ entry
    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(42)
        if options["flush"]:
            self.flush()
        cities, districts, cats, brands = self.seed_catalog()
        users = self.seed_users(cities, districts)
        L = self.seed_listings(cities, districts, cats, brands, users)
        convos = self.seed_chat(users, L)
        self.seed_reports(users, L, convos)
        self.seed_misc(users, L)

        s = self.style.SUCCESS
        self.stdout.write(s("Seed complete."))
        self.stdout.write(f"  cities: {City.objects.count()}  districts: {District.objects.count()}  categories: {Category.objects.count()}  brands: {Brand.objects.count()}")
        self.stdout.write(f"  users: {User.objects.count()}  listings: {Listing.objects.count()} "
                          f"(live {Listing.objects.filter(status='live').count()}, pending {Listing.objects.filter(status='pending').count()}, "
                          f"rejected {Listing.objects.filter(status='rejected').count()}, sold {Listing.objects.filter(status='sold').count()})")
        self.stdout.write(f"  images: {ListingImage.objects.count()}  conversations: {Conversation.objects.count()}  messages: {Message.objects.count()}  reports: {Report.objects.count()}  plans: {Plan.objects.count()}")
        dev_code = settings.OTP_DEV_CODE or "(see console output)"
        self.stdout.write(s("Login hints:"))
        self.stdout.write(f"  Operator / admin: phone 09120000000  — Django admin password: admin — OTP: {dev_code}")
        self.stdout.write(f"  Parent (مریم ر.): phone 09123456789 — OTP: {dev_code}")
        self.stdout.write(f"  Official store:   phone 09128890878 — OTP: {dev_code}")
        self.stdout.write(f"  Any other phone registers a new account with OTP {dev_code} (SMS_BACKEND={settings.SMS_BACKEND}).")
