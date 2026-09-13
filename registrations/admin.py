from django.contrib import admin
from django.utils import timezone

from .forms import RegistrationAdminForm
from .models import Event, Registration


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "fee_bdt", "is_team_event", "order", "is_active")
    list_filter = ("kind", "is_team_event", "is_active")
    list_editable = ("fee_bdt", "order", "is_active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    form = RegistrationAdminForm
    list_display = (
        "serial_number", "reference", "full_name", "segment_names",
        "school", "phone", "status", "checked_in", "amount_bdt", "created_at",
    )
    list_filter = ("status", "school", "checked_in", "events")
    list_editable = ("checked_in",)
    search_fields = (
        "full_name", "email", "phone", "school__name",
        "serial_number",
    )
    autocomplete_fields = ("school",)
    readonly_fields = ("paid_at", "checked_in_at", "created_at", "updated_at")
    actions = [
        "mark_paid", "mark_confirmed", "mark_cancelled",
        "mark_checked_in", "mark_not_checked_in",
    ]

    def save_model(self, request, obj, form, change):
        # Auto-calculate the total from segments when the amount was left
        # at 0; a manually entered non-zero amount is always respected.
        events = list(form.cleaned_data.get("events") or [])
        if not obj.amount_bdt and events:
            obj.amount_bdt = sum(e.fee_bdt for e in events)
        super().save_model(request, obj, form, change)

    @admin.action(description="Mark selected as paid")
    def mark_paid(self, request, queryset):
        queryset.update(status=Registration.STATUS_PAID, paid_at=timezone.now())

    @admin.action(description="Mark selected as confirmed")
    def mark_confirmed(self, request, queryset):
        queryset.filter(
            status__in=[Registration.STATUS_PENDING, Registration.STATUS_PAID]
        ).update(
            status=Registration.STATUS_CONFIRMED, confirmed_at=timezone.now()
        )

    @admin.action(description="Mark selected as cancelled")
    def mark_cancelled(self, request, queryset):
        queryset.update(status=Registration.STATUS_CANCELLED)

    @admin.action(description="Mark selected as checked in")
    def mark_checked_in(self, request, queryset):
        queryset.update(checked_in=True, checked_in_at=timezone.now())

    @admin.action(description="Remove check-in from selected")
    def mark_not_checked_in(self, request, queryset):
        queryset.update(checked_in=False, checked_in_at=None)
