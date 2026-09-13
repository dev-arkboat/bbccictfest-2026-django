# Require a school on every registration.
#
# Run: uv run python manage.py migrate

import django.db.models.deletion
from django.db import migrations, models


def _assign_fallback_school(apps, schema_editor):
    """Point any school-less rows at a fallback school so the
    non-nullable alter succeeds without losing data."""
    Registration = apps.get_model("registrations", "Registration")
    School = apps.get_model("schools", "School")
    if not Registration.objects.filter(school__isnull=True).exists():
        return
    school, _ = School.objects.get_or_create(
        name="Unspecified School", defaults={"order": 9999}
    )
    Registration.objects.filter(school__isnull=True).update(school=school)


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("registrations", "0008_offline_registrations"),
        ("schools", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(_assign_fallback_school, _noop),
        migrations.AlterField(
            model_name="registration",
            name="school",
            field=models.ForeignKey(
                help_text="Participant's school. Required — drives CA dashboards and fest-day search.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="participants",
                to="schools.school",
            ),
        ),
    ]
