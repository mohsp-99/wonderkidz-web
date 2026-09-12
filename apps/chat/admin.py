from django.contrib import admin

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ("sender", "body", "is_system", "is_read", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "listing", "buyer", "seller", "last_message_at", "is_closed")
    list_filter = ("is_closed",)
    search_fields = ("listing__title", "buyer__phone", "seller__phone", "buyer__display_name", "seller__display_name")
    raw_id_fields = ("listing", "buyer", "seller")
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "is_system", "is_read", "created_at")
    list_filter = ("is_system", "is_read")
    search_fields = ("body",)
    raw_id_fields = ("conversation", "sender")
