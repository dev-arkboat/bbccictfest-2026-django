# Offline-only registrations: drop the bKash ledger, switch to admin-entered
# multi-segment rows with a mandatory integer serial.
#
# Run: uv run python manage.py migrate

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _normalize_serials(apps, schema_editor):
    """Make every existing serial castable to integer before the type change.

    - NULL/blank -> 1000 + pk
    - pure digits -> kept
    - anything else (e.g. "OFF-1", "GATE-1") -> digits inside, or 1000 + pk
    - collisions get bumped until unique.
    """
    Registration = apps.get_model("registrations", "Registration")
    used = set()
    for reg in Registration.objects.order_by("pk"):
        raw = (reg.serial_number or "").strip() if isinstance(reg.serial_number, str) else reg.serial_number
        candidate = None
        if isinstance(raw, int):
            candidate = raw
        elif isinstance(raw, str) and raw.isdigit():
            candidate = int(raw)
        elif isinstance(raw, str):
            digits = "".join(ch for ch in raw if ch.isdigit())
            if digits:
                try:
                    candidate = int(digits[-6:])
                except ValueError:
                    candidate = None
        if not candidate:
            candidate = 1000 + (reg.pk or 0)
        while candidate in used or Registration.objects.filter(serial_number=str(candidate)).exclude(pk=reg.pk).exists():
            candidate += 1
        used.add(candidate)
        Registration.objects.filter(pk=reg.pk).update(serial_number=str(candidate))


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("registrations", "0007_alter_registration_email"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="registration",
            name="unique_user_event_registration",
        ),
        migrations.AddField(
            model_name="registration",
            name="events",
            field=models.ManyToManyField(
                help_text="Segments this participant joined. Total fee auto-calculates from these.",
                related_name="registrations",
                to="registrations.event",
            ),
        ),
        migrations.AlterField(
            model_name="event",
            name="fee_bdt",
            field=models.PositiveIntegerField(default=0, help_text="Registration fee in BDT. 0 = free."),
        ),
        migrations.AlterField(
            model_name="registration",
            name="amount_bdt",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Total fee in BDT. Auto-calculated from segments when left at 0; editable.",
            ),
        ),
        migrations.AlterField(
            model_name="registration",
            name="status",
            field=models.CharField(
                choices=[("pending", "Pending"), ("paid", "Paid"), ("confirmed", "Confirmed"), ("cancelled", "Cancelled")],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="registration",
            name="user",
            field=models.ForeignKey(
                blank=True,
                help_text="Linked account, if any. Optional — offline rows usually have none.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="registrations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # Normalize legacy string serials while the column is still varchar.
        migrations.RunPython(_normalize_serials, _noop),
        migrations.AlterField(
            model_name="registration",
            name="serial_number",
            field=models.PositiveIntegerField(
                default=1,
                help_text="Serial number from the offline paper form. Required, unique.",
                unique=True,
            ),
            preserve_default=False,
        ),
        migrations.RemoveField(
            model_name="registration",
            name="bkash_customer_msisdn",
        ),
        migrations.RemoveField(
            model_name="registration",
            name="bkash_payment_id",
        ),
        migrations.RemoveField(
            model_name="registration",
            name="bkash_trx_id",
        ),
        migrations.RemoveField(
            model_name="registration",
            name="event",
        ),
        migrations.RemoveField(
            model_name="registration",
            name="group_id",
        ),
        migrations.RemoveField(
            model_name="registration",
            name="institution",
        ),
        migrations.DeleteModel(
            name="PaymentTransaction",
        ),
    ]
