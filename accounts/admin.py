from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import LoginCode, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("name", "email", "hall", "room", "phone", "profile_complete", "is_active")
    list_filter = ("hall", "profile_complete", "is_active", "is_staff")
    search_fields = ("name", "email", "phone", "room")
    ordering = ("name",)
    readonly_fields = ("date_joined", "last_login")
    fieldsets = (
        (None, {"fields": ("email", "name")}),
        ("Campus", {"fields": ("hall", "room", "phone", "avatar")}),
        ("Status", {"fields": ("profile_complete", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "name", "password1", "password2")}),)


@admin.register(LoginCode)
class LoginCodeAdmin(admin.ModelAdmin):
    list_display = ("email", "code", "created_at", "expires_at", "attempts", "used_at")
    search_fields = ("email",)
    readonly_fields = ("email", "code", "created_at", "expires_at", "attempts", "used_at")
