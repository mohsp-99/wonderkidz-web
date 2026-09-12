from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.generic import TemplateView

from apps.listings.sitemaps import CategorySitemap, ListingSitemap, StaticSitemap

sitemaps = {"static": StaticSitemap, "categories": CategorySitemap, "listings": ListingSitemap}

urlpatterns = [
    path("admin/", admin.site.urls),
    path("panel/", include("apps.moderation.urls")),
    path("", include("apps.accounts.urls")),
    path("chat/", include("apps.chat.urls")),
    path("pay/", include("apps.payments.urls")),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
    ),
    path(
        "manifest.webmanifest",
        TemplateView.as_view(
            template_name="manifest.webmanifest", content_type="application/manifest+json"
        ),
    ),
    path("sw.js", TemplateView.as_view(template_name="sw.js", content_type="application/javascript")),
    path("", include("apps.listings.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "وندرکیدز — مدیریت"
admin.site.site_title = "وندرکیدز"
admin.site.index_title = "پنل مدیریت"
