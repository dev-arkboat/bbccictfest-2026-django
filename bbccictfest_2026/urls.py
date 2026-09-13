from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from bbccictfest_2026.sitemaps import (
    AmbassadorSitemap,
    ArcadeSitemap,
    BlogSitemap,
    StaticSitemap,
    VolunteerSitemap,
)

sitemaps = {
    "static": StaticSitemap,
    "arcade": ArcadeSitemap,
    "blog": BlogSitemap,
    "volunteers": VolunteerSitemap,
    "ambassadors": AmbassadorSitemap,
}

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("register/", include("registrations.urls")),
    path("volunteers/", include("volunteers.urls")),
    path("blog/", include("blog.urls")),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("", include("pwa.urls")),
    path("", include("core.urls")),
]
