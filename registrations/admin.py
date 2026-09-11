from django.contrib import admin
from django.utils import timezone

from .models import Event, PaymentTransaction, Registration


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "fee_bdt", "is_team_event", "order", "is_active")
    list_filter = ("kind", "is_team_event", "is_active")
    list_editable = ("fee_bdt", "order", "is_active")
    prepopulated_fields = {"slug": ("name",)}


class PaymentTransactionInline(admin.TabularInline):
    model = PaymentTransaction
    extra = 0
    readonly_fields = (
        "payment_id", "trx_id", "amount_bdt", "status",
        "payer_reference", "bkash_url", "error", "created_at",
    )
    can_delete = False


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = (
        "reference", "full_name", "event", "school", "phone", "status",
        "checked_in", "amount_bdt", "bkash_trx_id", "created_at",
    )
    list_filter = ("event", "status", "school", "checked_in")
    list_editable = ("checked_in",)
    search_fields = (
        "full_name", "email", "phone", "institution", "school__name",
        "serial_number", "bkash_trx_id", "bkash_payment_id",
    )
    readonly_fields = (
        "user", "event", "amount_bdt", "bkash_payment_id", "bkash_trx_id",
        "bkash_customer_msisdn", "paid_at", "checked_in_at", "created_at", "updated_at",
    )
    autocomplete_fields = ("school",)
    inlines = [PaymentTransactionInline]
    actions = ["mark_confirmed", "mark_cancelled", "mark_checked_in", "mark_not_checked_in"]

    @admin.action(description="Mark selected as confirmed")
    def mark_confirmed(self, request, queryset):
        queryset.filter(status__in=["paid", "pending"]).update(
            status=Registration.STATUS_CONFIRMED, confirmed_at=timezone.now()
        )

    @admin.action(description="Mark selected as cancelled")
    def mark_cancelled(self, request, queryset):
        queryset.update(status=Registration.STATUS_CANCELLED)

    @admin.action(description="Mark selected as checked in")
    def mark_checked_in(self, request, queryset):
        from django.utils import timezone

        queryset.update(checked_in=True, checked_in_at=timezone.now())

    @admin.action(description="Remove check-in from selected")
    def mark_not_checked_in(self, request, queryset):
        queryset.update(checked_in=False, checked_in_at=None)


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("payment_id", "registration", "amount_bdt", "status", "trx_id", "created_at")
    list_filter = ("status",)
    search_fields = ("payment_id", "trx_id", "registration__full_name")
    readonly_fields = (
        "registration", "payment_id", "trx_id", "amount_bdt", "status",
        "payer_reference", "bkash_url", "raw_create", "raw_execute",
        "raw_query", "error", "created_at", "updated_at",
    )

    def has_add_permission(self, request):
        return False
