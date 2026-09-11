from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "institution", "phone", "updated_at")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email", "institution", "phone")
    list_editable = ("role",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("user", "role")}),
        ("Contact & School", {"fields": ("phone", "institution", "class_name")}),
        ("Public page", {"fields": ("avatar_url", "bio")}),
        ("Meta", {"fields": ("created_at", "updated_at")}),
    )
