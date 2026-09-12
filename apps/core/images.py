"""On-upload image pipeline: validate, auto-orient, resize to standard sizes, encode WebP."""
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 12 * 1024 * 1024


class InvalidImage(Exception):
    pass


def open_image(uploaded_file) -> Image.Image:
    if uploaded_file.size > MAX_UPLOAD_BYTES:
        raise InvalidImage("حجم عکس بیش از ۱۲ مگابایت است.")
    try:
        img = Image.open(uploaded_file)
        img.load()
    except (UnidentifiedImageError, OSError):
        raise InvalidImage("فایل عکس معتبر نیست.")
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    return img


def make_variant(img: Image.Image, size, quality=82) -> ContentFile:
    out = img.copy()
    out.thumbnail(size, Image.LANCZOS)
    if out.mode == "RGBA":
        bg = Image.new("RGB", out.size, (255, 255, 255))
        bg.paste(out, mask=out.split()[3])
        out = bg
    buf = BytesIO()
    out.save(buf, "WEBP", quality=quality, method=4)
    return ContentFile(buf.getvalue())


def process_upload(uploaded_file):
    """Return dict of variant name -> ContentFile (webp) plus width/height of the gallery size."""
    img = open_image(uploaded_file)
    variants = {}
    for name, size in settings.IMAGE_SIZES.items():
        variants[name] = make_variant(img, size)
    return variants, img.size
