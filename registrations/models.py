from django.conf import settings
from django.db import models
from django.urls import reverse


class Event(models.Model):
    """A registrable fest segment with its fee.

    Fees are data (not hardcoded) so organizers can change them anytime.
    Free events cost 0. Registrations are offline-only: rows are created
    from the admin panel, never from a public form or payment gateway.
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
        default=0, help_text="Registration fee in BDT. 0 = free."
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
        # No per-event public registration page anymore — all signups are
        # offline. Point at the offline-only registration info page.
        return reverse("registrations:events")

    @property
    def is_free(self):
        return self.fee_bdt == 0


class Registration(models.Model):
    """One offline registration row, created from the admin panel.

    A row covers one participant across one or more segments (events).
    ``amount_bdt`` auto-calculates as the sum of the chosen segments'
    fees but stays manually editable in admin.
    """

    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_CONFIRMED = "confirmed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    CLASS_CHOICES = [
        ("6", "Class 6"),
        ("7", "Class 7"),
        ("8", "Class 8"),
        ("9", "Class 9"),
        ("10", "Class 10"),
        ("Other", "Other"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="registrations",
        null=True, blank=True,
        help_text="Linked account, if any. Optional — offline rows usually have none.",
    )
    events = models.ManyToManyField(
        Event,
        related_name="registrations",
        help_text="Segments this participant joined. Total fee auto-calculates from these.",
    )
    # Mandatory, unique paper-form serial.
    serial_number = models.PositiveIntegerField(
        unique=True,
        help_text="Serial number from the offline paper form. Required, unique.",
    )
    full_name = models.CharField(max_length=160)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=20)
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.PROTECT,
        related_name="participants",
        help_text="Participant's school. Required — drives CA dashboards and fest-day search.",
    )
    class_name = models.CharField("Class", max_length=50, choices=CLASS_CHOICES)
    # Team-event extras (science showdown).
    team_name = models.CharField(max_length=160, blank=True)
    teammate_name = models.CharField("Teammate name", max_length=160, blank=True)
    teacher_name = models.CharField("Teacher name", max_length=160, blank=True)
    address = models.CharField(max_length=255, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    amount_bdt = models.PositiveIntegerField(
        default=0,
        help_text="Total fee in BDT. Auto-calculated from segments when left at 0; editable.",
    )

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

    def __str__(self):
        return f"{self.reference} — {self.full_name} (Serial {self.serial_number})"

    @property
    def reference(self):
        return f"BBCC26-{self.pk or 0:05d}"

    @property
    def is_paid(self):
        return self.status in {self.STATUS_PAID, self.STATUS_CONFIRMED}

    @property
    def calculated_amount(self):
        """Sum of the chosen segments' fees."""
        return sum(e.fee_bdt for e in self.events.all())

    def segment_names(self):
        return ", ".join(e.name for e in self.events.all())
    segment_names.short_description = "Segments"
