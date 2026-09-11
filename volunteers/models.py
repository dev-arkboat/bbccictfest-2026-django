from django.db import models
from django.urls import reverse


class Volunteer(models.Model):
    """Fest volunteers — added easily from the admin panel."""

    name = models.CharField(max_length=160)
    role = models.CharField(
        max_length=160, default="Volunteer",
        help_text="e.g. Volunteer — Logistics",
    )
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="volunteers",
        help_text="The volunteer's school. Each school's volunteers appear under its Campus Ambassador.",
    )
    image_url = models.URLField("Photo URL", max_length=500, blank=True)
    bio = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    facebook_url = models.URLField(max_length=500, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.name} — {self.role}"

    def get_absolute_url(self):
        return reverse("volunteers:detail", kwargs={"pk": self.pk})

    @property
    def initials(self):
        parts = [p for p in self.name.split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()
