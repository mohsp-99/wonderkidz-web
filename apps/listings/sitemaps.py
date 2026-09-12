from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.catalog.models import Category

from .models import Listing


class StaticSitemap(Sitemap):
    priority = 0.6
    changefreq = "weekly"

    def items(self):
        return ["listings:home", "listings:search"]

    def location(self, item):
        return reverse(item)


class CategorySitemap(Sitemap):
    priority = 0.8
    changefreq = "daily"

    def items(self):
        return Category.objects.all()


class ListingSitemap(Sitemap):
    priority = 0.7
    changefreq = "daily"

    def items(self):
        return Listing.objects.filter(status=Listing.Status.LIVE)

    def lastmod(self, obj):
        return obj.updated_at
