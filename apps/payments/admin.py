from django.contrib import admin

from .models import Payment, Plan


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "price", "duration_days", "is_active")
    list_editable = ("price", "is_active")
    list_filter = ("kind", "is_active")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "plan", "amount", "gateway", "status", "ref_id", "created_at", "paid_at")
    list_filter = ("status", "gateway", "plan")
    search_fields = ("user__phone", "authority", "ref_id")
    readonly_fields = [f.name for f in Payment._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
