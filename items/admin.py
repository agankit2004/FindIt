from django.contrib import admin

from .models import Category, Item, ItemPhoto, Location, Match, Notification


class PhotoInline(admin.TabularInline):
    model = ItemPhoto
    extra = 0


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("ref", "title", "kind", "category", "location", "happened_on", "status", "reporter")
    list_filter = ("kind", "status", "category", "location__zone", "happened_on")
    search_fields = ("title", "description", "brand", "colour", "reporter__name", "reporter__email")
    date_hierarchy = "created_at"
    inlines = [PhotoInline]
    actions = ["close_items"]

    @admin.action(description="Close selected reports")
    def close_items(self, request, queryset):
        n = queryset.update(status=Item.CLOSED)
        self.message_user(request, f"{n} report(s) closed.")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "glyph", "order")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "zone")
    list_filter = ("zone",)
    search_fields = ("name",)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("lost_item", "found_item", "score", "source", "dismissed", "created_at")
    list_filter = ("source", "dismissed")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "text", "read", "created_at")
    list_filter = ("read",)
