"""One-shot production bootstrap: CMS content + admin user. Idempotent.

Seeds every database entry the site needs (via ``seed_site``), then ensures
an admin superuser exists from environment variables — ``createsuperuser``
is interactive and unusable in deploy scripts.

Run: uv run python manage.py setup_production
Env:
  DJANGO_SUPERUSER_USERNAME (default "admin")
  DJANGO_SUPERUSER_EMAIL (default "")
  DJANGO_SUPERUSER_PASSWORD (required — command refuses to run without it)
"""

import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Seed all site content and ensure an admin superuser (production bootstrap)."

    def handle(self, *args, **options):
        from django.conf import settings as dj_settings

        if getattr(dj_settings, "DEBUG", False):
            self.stdout.write(
                self.style.WARNING("WARNING: DEBUG is on — turn it off in production.")
            )
        secret = getattr(dj_settings, "SECRET_KEY", "")
        if secret.startswith("django-insecure-"):
            self.stdout.write(
                self.style.WARNING(
                    "WARNING: default insecure SECRET_KEY detected — set a real one."
                )
            )

        call_command("seed_site", verbosity=options.get("verbosity", 1))

        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin").strip() or "admin"
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        if not password:
            raise CommandError(
                "Refusing to continue: set DJANGO_SUPERUSER_PASSWORD in the environment."
            )

        User = get_user_model()
        with transaction.atomic():
            user, created = User.objects.update_or_create(
                username=username,
                defaults={"email": email, "is_staff": True, "is_superuser": True},
            )
            user.set_password(password)
            user.save(update_fields=["password"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Admin user '{username}': {'created' if created else 'password reset'}."
            )
        )
        self.stdout.write("Next: collectstatic and point DNS at this server.")
