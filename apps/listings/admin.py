from django.contrib import admin

from .models import Listing, ListingImage, PhoneReveal, Report, SavedListing


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 0
    fields = ("image", "thumb", "order")


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "status", "price", "category", "district", "published_at")
    list_filter = ("status", "category", "city", "condition", "age_range")
    search_fields = ("title", "code", "owner__phone")
    readonly_fields = ("code", "search_text", "auto_flags", "views_count", "reveals_count", "created_at", "updated_at")
    inlines = [ListingImageInline]
    actions = ["approve", "reject"]
    date_hierarchy = "created_at"

    @admin.action(description="تأیید و انتشار")
    def approve(self, request, queryset):
        for lst in queryset:
            lst.publish(by=request.user)

    @admin.action(description="رد کردن")
    def reject(self, request, queryset):
        for lst in queryset:
            lst.reject("رد شده توسط مدیر", by=request.user)


@admin.register(SavedListing)
class SavedListingAdmin(admin.ModelAdmin):
    list_display = ("user", "listing", "created_at")


@admin.register(PhoneReveal)
class PhoneRevealAdmin(admin.ModelAdmin):
    list_display = ("user", "listing", "created_at")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("target_title", "reason", "reporter", "priority", "status", "created_at")
    list_filter = ("status", "priority", "reason")
