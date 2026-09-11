from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _ensure_groups(**kwargs):
    """Create layered role groups (Organizer / Volunteer) with sensible perms.

    Layer hierarchy (low -> high): participant < volunteer < organizer < superuser.
    - Volunteer: view-only on registrations + volunteers.
    - Organizer: full control over fest content (core CMS, registrations,
      blog posts/comments, volunteers, CA applications) but no auth/admin rights.
    Runs on post_migrate (never touches the DB during app init).
    """
    from django.contrib.auth.models import Group, Permission

    organizer, _ = Group.objects.get_or_create(name="Organizer")
    volunteer, _ = Group.objects.get_or_create(name="Volunteer")

    organizer_codenames = {
        "view_registration", "change_registration",
        "view_paymenttransaction",
        "view_campusambassadorapplication", "change_campusambassadorapplication",
        "add_post", "change_post", "delete_post", "view_post",
        "view_comment", "change_comment", "delete_comment",
        "add_volunteer", "change_volunteer", "delete_volunteer", "view_volunteer",
        "view_review", "change_review",
    }
    volunteer_codenames = {
        "view_registration",
        "view_volunteer",
    }
    organizer.permissions.set(
        Permission.objects.filter(codename__in=organizer_codenames)
    )
    volunteer.permissions.set(
        Permission.objects.filter(codename__in=volunteer_codenames)
    )


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Accounts & Roles"

    def ready(self):
        from . import signals  # noqa: F401

        post_migrate.connect(_ensure_groups, sender=self)
