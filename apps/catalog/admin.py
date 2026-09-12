from django.contrib import admin

from .models import Brand, Category, City, District


class DistrictInline(admin.TabularInline):
    model = District
    extra = 0


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "order")
    list_editable = ("is_active", "order")
    inlines = [DistrictInline]


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "is_active", "order")
    list_filter = ("city",)
    list_editable = ("is_active", "order")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("__str__", "slug", "emoji", "order")
    list_filter = ("parent",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_featured", "order")
    list_editable = ("is_featured", "order")
