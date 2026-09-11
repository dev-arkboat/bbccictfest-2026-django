"""Dynamic sitemaps — /sitemap.xml is generated from the database."""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return ["core:home", "core:arcade", "core:reviews", "registrations:events",
                "registrations:ca_list", "volunteers:list", "blog:list"]

    def location(self, item):
        return reverse(item)


class VolunteerSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        from volunteers.models import Volunteer

        return Volunteer.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.joined_at


class AmbassadorSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        from django.contrib.auth import get_user_model

        from accounts.models import Role

        return (
            get_user_model()
            .objects.filter(profile__role=Role.CAMPUS_AMBASSADOR)
            .select_related("profile")
        )

    def location(self, obj):
        return reverse("registrations:ca_detail", kwargs={"pk": obj.pk})

    def lastmod(self, obj):
        profile = getattr(obj, "profile", None)
        return getattr(profile, "updated_at", None)


class ArcadeSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        from core.models import Game

        return Game.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.updated_at


class EventSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        from registrations.models import Event

        return Event.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.updated_at


class BlogSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        from blog.models import Post

        return Post.objects.filter(status=Post.STATUS_PUBLISHED)

    def lastmod(self, obj):
        return obj.updated_at
