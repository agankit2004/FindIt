from django.contrib import admin

from .models import Claim, ClaimEvent, ClaimMessage


class EventInline(admin.TabularInline):
    model = ClaimEvent
    extra = 0
    readonly_fields = ("actor", "from_status", "to_status", "note", "created_at")


class MessageInline(admin.TabularInline):
    model = ClaimMessage
    extra = 0
    readonly_fields = ("sender", "body", "created_at")


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ("ref", "item", "claimant", "status", "created_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("item__title", "claimant__name", "claimant__email", "proof")
    inlines = [EventInline, MessageInline]
