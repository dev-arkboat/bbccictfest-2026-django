from django.db import models
from django.utils.text import slugify


class School(models.Model):
    """A school/college. Campus Ambassadors must belong to one; volunteers
    are grouped under their school so each CA sees their own team."""

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    address = models.CharField(max_length=255, blank=True)
    logo_url = models.URLField("Logo URL", max_length=500, blank=True)
    contact_email = models.EmailField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:180] or "school"
            slug, i = base, 2
            while School.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)
