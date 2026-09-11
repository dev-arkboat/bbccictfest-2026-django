from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_personreview"),
    ]

    operations = [
        migrations.RenameField(
            model_name="sitesetting",
            old_name="registration_open",
            new_name="register_status",
        ),
    ]
