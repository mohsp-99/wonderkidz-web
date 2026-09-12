from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import OTPCode, SavedSearch, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("-date_joined",)
    list_display = ("phone", "display_name", "account_type", "is_verified", "is_banned", "date_joined")
    list_filter = ("account_type", "is_banned", "is_verified", "is_staff")
    search_fields = ("phone", "display_name")
    readonly_fields = ("date_joined", "last_login", "last_seen")
    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("پروفایل", {"fields": ("display_name", "account_type", "city", "district")}),
        ("وضعیت", {"fields": ("is_verified", "is_active", "is_banned", "ban_reason", "warnings_count", "listing_cap")}),
        ("اعلان‌ها", {"fields": ("notify_moderation", "notify_chat", "notify_saved_search")}),
        ("دسترسی", {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        ("زمان‌ها", {"fields": ("date_joined", "last_login", "last_seen")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("phone", "display_name", "password1", "password2", "is_staff")}),
    )
    filter_horizontal = ("groups", "user_permissions")


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display = ("phone", "code", "created_at", "expires_at", "attempts", "used")
    search_fields = ("phone",)
    readonly_fields = ("phone", "code", "created_at", "expires_at", "attempts", "used")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SavedSearch)
class SavedSearchAdmin(admin.ModelAdmin):
    list_display = ("label", "user", "querystring", "created_at")
    search_fields = ("label", "user__phone")
