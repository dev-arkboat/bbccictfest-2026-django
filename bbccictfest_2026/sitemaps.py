"""Dynamic sitemaps — /sitemap.xml is generated from the database."""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return ["core:home", "core:arcade", "core:reviews", "registrations:events",
                "registrations:ca_apply", "registrations:ca_list", "volunteers:list", "blog:list"]

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
        from registrations.models import CampusAmbassadorApplication

        return CampusAmbassadorApplication.objects.filter(
            status=CampusAmbassadorApplication.STATUS_APPROVED
        )

    def lastmod(self, obj):
        return obj.updated_at


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
