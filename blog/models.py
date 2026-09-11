from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class Post(models.Model):
    """Blog post — published from the admin panel by staff/organizers."""

    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PUBLISHED, "Published"),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    excerpt = models.CharField(max_length=300, blank=True)
    content = models.TextField()
    cover_image_url = models.URLField("Cover image URL", max_length=500, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blog_posts"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:180] or "post"
            slug, i = base, 2
            while Post.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        if self.status == self.STATUS_PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("blog:detail", kwargs={"slug": self.slug})

    @property
    def is_published(self):
        return self.status == self.STATUS_PUBLISHED

    def likes_count(self):
        return self.likes.count()

    @property
    def reading_time_minutes(self):
        """Rough read time at 200 wpm, minimum 1 minute. No migration needed."""
        words = len((self.content or "").split())
        return max(1, round(words / 200))

    def user_has_liked(self, user):
        if not getattr(user, "is_authenticated", False):
            return False
        return self.likes.filter(user=user).exists()

    def visible_comments(self):
        return self.comments.filter(is_approved=True).select_related("author")


class Comment(models.Model):
    """Any logged-in user can comment on a published post."""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blog_comments"
    )
    body = models.TextField(max_length=1000)
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author.get_username()} on {self.post.title}"


class Like(models.Model):
    """Like toggle — one per user per post."""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blog_likes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["post", "user"], name="unique_post_user_like")
        ]

    def __str__(self):
        return f"{self.user.get_username()} likes {self.post.title}"
