from django.contrib import admin

from .models import ModerationDecision


@admin.register(ModerationDecision)
class ModerationDecisionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "decision", "listing_title", "reason", "operator", "target_user")
    list_filter = ("decision", "operator")
    search_fields = ("listing_title", "reason", "target_user__phone")
    readonly_fields = ("created_at", "listing", "report", "target_user", "operator", "decision", "reason", "listing_title")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
