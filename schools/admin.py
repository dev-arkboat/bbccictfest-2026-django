from django.contrib import admin

from .models import School


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "is_active", "updated_at")
    list_filter = ("is_active",)
    list_editable = ("order", "is_active")
    search_fields = ("name", "address")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
