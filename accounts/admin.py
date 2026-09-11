from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "school", "institution", "phone", "updated_at")
    list_filter = ("role", "school")
    search_fields = ("user__username", "user__email", "institution", "phone")
    list_editable = ("role",)
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("school",)
    fieldsets = (
        (None, {"fields": ("user", "role", "school")}),
        ("Contact & School", {"fields": ("phone", "institution", "class_name")}),
        ("Public page", {"fields": ("avatar_url", "bio")}),
        ("Meta", {"fields": ("created_at", "updated_at")}),
    )
