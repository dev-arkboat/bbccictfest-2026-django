from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from datetime import datetime, timedelta
from datetime import timezone as dt_timezone


def default_event_date():
    # Sept 19, 2026, 09:00 Dhaka time (+06:00) — fest day.
    return datetime(2026, 9, 19, 9, 0, tzinfo=dt_timezone(timedelta(hours=6)))


class SiteSetting(models.Model):
    """Singleton row holding every global, editable bit of site copy.

    Everything on the landing page that is not a list lives here so admins
    can change the full site without touching code.
    """

    site_name = models.CharField(max_length=120, default="BBCC ICT Fest 2026")
    org_name = models.CharField(max_length=160, default="Bindubasini Boys' Computer Club")
    tagline = models.CharField(max_length=200, default="Biggest ICT Festival in Tangail")
    hero_kicker = models.CharField(max_length=120, default="Registrations are Open")
    hero_title_line1 = models.CharField(max_length=120, default="ICT FEST")
    hero_title_line2 = models.CharField(max_length=120, default="2026")
    hero_subtitle = models.TextField(
        default="Tangail's biggest technology festival — five competitions, "
        "extraordinary guests, and a full day of innovation."
    )
    event_date = models.DateTimeField(default=default_event_date)
    venue_name = models.CharField(max_length=160, default="Bindubasini Boys' School, Tangail")
    venue_address = models.CharField(max_length=255, default="Bindubasini Boys' School, Tangail, Bangladesh")
    participants_label = models.CharField(max_length=60, default="1000+ Participants")
    contact_email = models.EmailField(default="club.bbcc@gmail.com")
    facebook_url = models.URLField(max_length=500, default="https://www.facebook.com/bbcompuerclub")
    footer_about = models.TextField(
        default="The Biggest ICT Festival in Tangail District. Organized by "
        "Bindubasini Boys' Computer Club bringing technology and innovation "
        "to the forefront of education."
    )
    made_by_name = models.CharField(max_length=120, default="Md Abu Salehin")
    made_by_url = models.URLField(max_length=500, default="https://mdsalehin.netlify.app/")
    meta_description = models.TextField(
        default="Tangail's biggest ICT festival — ICT Quiz, Science Project "
        "Showdown, Coding Competition, Chess & Rubik's Cube. September 19, 2026 "
        "at Bindubasini Boys' School. Register now!"
    )
    og_image_url = models.URLField(
        "Social share image URL", max_length=500,
        default="https://bbccictfest.pro.bd/logo.png",
    )
    register_status = models.BooleanField("Registration open", default=True)
    ca_open = models.BooleanField("Campus Ambassador applications open", default=True)
    about_heading_a = models.CharField(
        max_length=200, default="The Biggest ICT Event"
    )
    about_heading_b = models.CharField(
        max_length=200, default="In the History of Tangail District"
    )
    about_para1 = models.TextField(
        default="Bindubasini Boys' Computer Club presents the inaugural ICT Fest — "
        "a landmark event uniting students, educators, and innovators from across "
        "Tangail for a celebration of technology and creativity."
    )
    about_para2 = models.TextField(
        default="With five distinct competitions — ICT Quiz, Science Project Showdown, "
        "Coding Competition, Chess, Rubik's Cube — plus distinguished guests and "
        "school exhibitions, this is the largest technology festival the district "
        "has ever witnessed."
    )
    cta_tag = models.CharField(max_length=60, default="Are You")
    cta_title_a = models.CharField(max_length=200, default="Ready to Be Part of")
    cta_title_b = models.CharField(max_length=200, default="The Biggest ICT Fest?")
    cta_subtitle = models.TextField(
        default="Registrations are open. Secure your spot at Tangail's biggest "
        "technology celebration!"
    )
    ca_heading = models.CharField(max_length=200, default="Become a Campus Ambassador")
    ca_description = models.TextField(
        default="Represent BBCC ICT Fest 2026 at your school or college. Lead "
        "promotions, build your network, and earn exclusive perks — certificate, "
        "crest, and priority access on fest day."
    )
    committee_note = models.CharField(max_length=255, default="Photos coming soon")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site setting"
        verbose_name_plural = "Site settings"

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce singleton
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class HeroChip(models.Model):
    """Floating code chips on the hero (e.g. `$ fest --kickoff --sep-19`)."""

    html = models.CharField(max_length=255, help_text="Inline HTML allowed, e.g. $ <b>fest</b> --kickoff")
    css_class = models.CharField(max_length=20, default="chip-1", help_text="chip-1 … chip-4")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Chip {self.css_class}: {self.html[:40]}"


class TickerItem(models.Model):
    html = models.CharField(max_length=255, help_text="Inline HTML allowed, e.g. ICT QUIZ or <b>1000+</b> PARTICIPANTS")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.html[:60]


class Stat(models.Model):
    value = models.PositiveIntegerField(default=0, help_text="Animated counter target")
    suffix = models.CharField(max_length=10, default="", blank=True, help_text="e.g. +")
    label = models.CharField(max_length=80)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.value}{self.suffix} {self.label}"


class Competition(models.Model):
    title = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    icon_svg = models.TextField(
        help_text="Inline SVG (inner content of the icon). Keep stroke='currentColor'.",
        blank=True,
    )
    icon_class = models.CharField(max_length=20, default="comp-icon-1")
    description = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class CompetitionTag(models.Model):
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name="tags")
    text = models.CharField(max_length=80)
    highlight = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.competition.title}: {self.text}"


class CompetitionDetail(models.Model):
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name="details")
    text = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.competition.title}: {self.text[:50]}"


class TimelineStep(models.Model):
    step_no = models.PositiveIntegerField(default=1)
    tag = models.CharField(max_length=60, help_text="e.g. Step 01 Register")
    title = models.CharField(max_length=160)
    text = models.TextField()
    dot_class = models.CharField(max_length=20, default="tl-dot-1")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.step_no}. {self.title}"


class Guest(models.Model):
    name = models.CharField(max_length=160)
    role = models.CharField(max_length=120, help_text="e.g. Chief Guest")
    bio = models.TextField(blank=True)
    image_url = models.URLField("Photo URL", max_length=500, blank=True)
    avatar_class = models.CharField(max_length=10, default="g-a1")
    is_featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.name} ({self.role})"

    @property
    def initials(self):
        parts = [p for p in self.name.replace("?", "").split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()


class CommitteeCategory(models.Model):
    name = models.CharField(max_length=160, help_text="e.g. Adviser Panel (Teachers)")
    slug = models.SlugField(unique=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name_plural = "Committee categories"

    def __str__(self):
        return self.name


class CommitteeMember(models.Model):
    category = models.ForeignKey(
        CommitteeCategory, on_delete=models.CASCADE, related_name="members"
    )
    name = models.CharField(max_length=160)
    role = models.CharField(max_length=160)
    image_url = models.URLField("Photo URL", max_length=500, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.name} — {self.role}"

    @property
    def initials(self):
        parts = [p for p in self.name.split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()


class Sponsor(models.Model):
    name = models.CharField(max_length=160)
    url = models.URLField(max_length=500, blank=True)
    is_surprise = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class FAQ(models.Model):
    question = models.CharField(max_length=255)
    answer = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"

    def __str__(self):
        return self.question


class Game(models.Model):
    """One card on the BBCC Arcade listing + its play page."""

    title = models.CharField(max_length=120)
    slug = models.SlugField(unique=True, help_text="Matches the legacy file name, e.g. snake")
    description = models.TextField()
    difficulty = models.CharField(max_length=40, default="Easy")
    icon_svg = models.TextField(
        blank=True, help_text="Inline SVG for the arcade card icon (inner <svg>…</svg>)."
    )
    icon_class = models.CharField(max_length=10, default="g-1", help_text="g-1 … g-25")
    accent_color = models.CharField(max_length=20, default="#FF7A1A")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("core:game_play", kwargs={"slug": self.slug})


class Review(models.Model):
    """One 5-star review per logged-in user (editable afterwards)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="review"
    )
    rating = models.PositiveSmallIntegerField(
        choices=[(i, f"{i} star{'s' if i > 1 else ''}") for i in range(1, 6)],
        default=5,
    )
    comment = models.TextField(max_length=1000)
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user.get_username()} — {self.rating}/5"

    def clean(self):
        if not 1 <= (self.rating or 0) <= 5:
            raise ValidationError("Rating must be between 1 and 5.")


class PersonReview(models.Model):
    """A 5-star rating + comment for one volunteer or one ambassador.

    Same rules as the event review: visible to everyone, one per logged-in
    user per person, editable afterwards. Exactly one of `volunteer` /
    `ambassador` must be set.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="person_reviews"
    )
    volunteer = models.ForeignKey(
        "volunteers.Volunteer",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="person_reviews",
    )
    ambassador = models.ForeignKey(
        "registrations.CampusAmbassadorApplication",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="person_reviews",
    )
    rating = models.PositiveSmallIntegerField(
        choices=[(i, f"{i} star{'s' if i > 1 else ''}") for i in range(1, 6)],
        default=5,
    )
    comment = models.TextField(max_length=1000)
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "volunteer"], name="unique_user_volunteer_review"
            ),
            models.UniqueConstraint(
                fields=["user", "ambassador"], name="unique_user_ambassador_review"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(volunteer__isnull=True, ambassador__isnull=False)
                    | models.Q(volunteer__isnull=False, ambassador__isnull=True)
                ),
                name="person_review_single_target",
            ),
        ]

    def __str__(self):
        target = self.volunteer or self.ambassador
        return f"{self.user.get_username()} on {target} — {self.rating}/5"

    @property
    def target(self):
        return self.volunteer or self.ambassador

    def clean(self):
        # NOTE: the exactly-one-target rule lives in the DB CheckConstraint,
        # not here — forms assign volunteer/ambassador after validation.
        if not 1 <= (self.rating or 0) <= 5:
            raise ValidationError("Rating must be between 1 and 5.")
