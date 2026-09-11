from django.conf import settings
from django.db import models
from django.urls import reverse


class Event(models.Model):
    """A registrable fest event with its bKash fee.

    Fees are data (not hardcoded) so organizers can change them anytime.
    Free events skip the payment gateway entirely.
    """

    KIND_CHOICES = [
        ("quiz", "ICT Quiz"),
        ("science", "Science Project Showdown"),
        ("coding", "Coding Competition"),
        ("chess", "Chess"),
        ("rubiks", "Rubik's Cube"),
    ]

    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="quiz")
    fee_bdt = models.PositiveIntegerField(
        default=0, help_text="Registration fee in BDT. 0 = free, skips bKash."
    )
    is_team_event = models.BooleanField(
        default=False, help_text="Science showdown: 2 students + 1 teacher."
    )
    short_description = models.TextField(blank=True)
    rules = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        if self.fee_bdt:
            return f"{self.name} ({self.fee_bdt} BDT)"
        return f"{self.name} (Free)"

    def get_absolute_url(self):
        return reverse("registrations:register", kwargs={"slug": self.slug})

    @property
    def is_free(self):
        return self.fee_bdt == 0


class Registration(models.Model):
    """One stored registration row per user per event.

    Guests (no login) get ``user=None`` — the UNIQUE (user, event) rule only
    binds logged-in users, since NULLs never collide. Rows created together
    in one multi-segment checkout share a ``group_id`` and are paid for with
    a single bKash transaction.
    """

    STATUS_PENDING = "pending"
    STATUS_PAYMENT_PENDING = "payment_pending"
    STATUS_PAID = "paid"
    STATUS_CONFIRMED = "confirmed"
    STATUS_CANCELLED = "cancelled"
    STATUS_REFUNDED = "refunded"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PAYMENT_PENDING, "Payment pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_REFUNDED, "Refunded"),
    ]

    CLASS_CHOICES = [
        ("6", "Class 6"),
        ("7", "Class 7"),
        ("8", "Class 8"),
        ("9", "Class 9"),
        ("10", "Class 10"),
        ("Other", "Other"),
    ]

    #: Statuses that still need money — safe to (re)pay as a group.
    PAYABLE_STATUSES = {STATUS_PENDING, STATUS_PAYMENT_PENDING}

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="registrations",
        null=True, blank=True,
        help_text="Linked account, if the person registered while logged in. Guests leave this empty.",
    )
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name="registrations")
    # Checkout grouping: one bKash payment can cover several rows at once.
    group_id = models.CharField(max_length=32, blank=True, db_index=True)
    # Pre-printed serial from offline paper forms (optional, must be unique).
    serial_number = models.CharField(
        max_length=50, null=True, blank=True, unique=True,
        help_text="Serial number from the offline paper form, if any.",
    )
    full_name = models.CharField(max_length=160)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="participants",
        help_text="Participant's school (drives CA dashboards and fest-day search).",
    )
    institution = models.CharField(max_length=200)
    class_name = models.CharField("Class", max_length=50, choices=CLASS_CHOICES)
    # Team-event extras (science showdown).
    team_name = models.CharField(max_length=160, blank=True)
    teammate_name = models.CharField("Teammate name", max_length=160, blank=True)
    teacher_name = models.CharField("Teacher name", max_length=160, blank=True)
    address = models.CharField(max_length=255, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    amount_bdt = models.PositiveIntegerField(default=0)

    # bKash bookkeeping (filled by the payment flow).
    bkash_payment_id = models.CharField(max_length=100, blank=True, db_index=True)
    bkash_trx_id = models.CharField(max_length=100, blank=True, db_index=True)
    bkash_customer_msisdn = models.CharField(max_length=20, blank=True)

    paid_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    # Fest-day gate: ticked when staff verify the person on entry.
    checked_in = models.BooleanField(default=False)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "event"], name="unique_user_event_registration")
        ]

    def __str__(self):
        return f"{self.reference} — {self.full_name} ({self.event.name})"

    @property
    def reference(self):
        return f"BBCC26-{self.pk or 0:05d}"

    @property
    def is_paid(self):
        return self.status in {self.STATUS_PAID, self.STATUS_CONFIRMED}

    def get_absolute_url(self):
        return reverse("registrations:detail", kwargs={"pk": self.pk})


class PaymentTransaction(models.Model):
    """Append-only ledger of every bKash step for a registration.

    This is what makes the payment system robust: create -> callback ->
    execute -> query are all stored with raw payloads, so any payment can
    be audited, retried, or reconciled from the admin.
    """

    STATUS_CHOICES = [
        ("initiated", "Initiated (create)"),
        ("callback_success", "Callback: success"),
        ("callback_fail", "Callback: failed"),
        ("callback_cancel", "Callback: cancelled"),
        ("executed", "Executed"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]

    registration = models.ForeignKey(
        Registration, on_delete=models.CASCADE, related_name="payments"
    )
    # Set when one bKash transaction covers a multi-segment checkout group.
    group_id = models.CharField(max_length=32, blank=True, db_index=True)
    payment_id = models.CharField(max_length=100, db_index=True)
    trx_id = models.CharField(max_length=100, blank=True, db_index=True)
    amount_bdt = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="initiated")
    payer_reference = models.CharField(max_length=160, blank=True)
    bkash_url = models.URLField(max_length=1000, blank=True)
    raw_create = models.JSONField(default=dict, blank=True)
    raw_execute = models.JSONField(default=dict, blank=True)
    raw_query = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.payment_id} [{self.status}]"
