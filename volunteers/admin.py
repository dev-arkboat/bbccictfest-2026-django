from django.contrib import admin
from django.utils.html import format_html

from .models import Volunteer


@admin.register(Volunteer)
class VolunteerAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "school", "order", "is_active", "page_link", "joined_at")
    list_filter = ("is_active", "school")
    list_editable = ("role", "order", "is_active")
    search_fields = ("name", "role", "bio")
    autocomplete_fields = ("school",)

    @admin.display(description="Public page")
    def page_link(self, obj):
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">volunteers/{}/ ↗</a>',
            obj.get_absolute_url(),
            obj.pk,
        )
