from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Role(models.TextChoices):
    PARTICIPANT = "participant", "Participant"
    VOLUNTEER = "volunteer", "Volunteer"
    ORGANIZER = "organizer", "Organizer"


#: Numeric rank for the layered admin system (higher = more power).
ROLE_RANK = {
    Role.PARTICIPANT: 0,
    Role.VOLUNTEER: 1,
    Role.ORGANIZER: 2,
}


def role_rank(user) -> int:
    """Return the admin-layer rank for a user.

    0 participant < 1 volunteer < 2 organizer < 3 superuser.
    Staff flag alone does not grant rank; superuser always tops.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return -1
    if getattr(user, "is_superuser", False):
        return 3
    profile = getattr(user, "profile", None)
    if profile is None:
        return 0
    return ROLE_RANK.get(profile.role, 0)


class Profile(models.Model):
    """Extended user profile with layered role + public page data.

    All images are URLField (per requirement — no local uploads).
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PARTICIPANT)
    phone = models.CharField(max_length=20, blank=True)
    institution = models.CharField(max_length=200, blank=True)
    class_name = models.CharField("Class", max_length=50, blank=True)
    avatar_url = models.URLField("Avatar image URL", max_length=500, blank=True)
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user.get_username()} ({self.get_role_display()})"

    @property
    def rank(self) -> int:
        if self.user.is_superuser:
            return 3
        return ROLE_RANK.get(self.role, 0)

    @property
    def is_volunteer_or_above(self) -> bool:
        return self.rank >= 1

    @property
    def is_organizer_or_above(self) -> bool:
        return self.rank >= 2 or self.user.is_staff
