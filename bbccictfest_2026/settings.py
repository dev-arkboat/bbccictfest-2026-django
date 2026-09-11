"""Django settings for bbccictfest_2026 — best-practice, env-driven config."""

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env first (python-dotenv as required). .env is git-ignored; see .env.example.
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _resolve_databases(database_url: str, sqlite_name: str, base_dir: Path) -> dict:
    """Build DATABASES from the environment.

    ``DATABASE_URL`` wins (Postgres in production, parsed by dj-database-url
    with persistent + health-checked connections). Empty/absent falls back to
    a local SQLite file. Relative sqlite paths always resolve against the
    project root so behaviour never depends on the working directory.
    """
    database_url = (database_url or "").strip()
    if not database_url:
        return {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": base_dir / sqlite_name,
            }
        }
    import dj_database_url

    config = dj_database_url.parse(
        database_url, conn_max_age=600, conn_health_checks=True
    )
    name = config.get("NAME", "")
    if (
        config.get("ENGINE") == "django.db.backends.sqlite3"
        and name not in (":memory:", "")
        and not os.path.isabs(name)
    ):
        config["NAME"] = str(base_dir / name)
    return {"default": config}


SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-olv%sk(e42o#g8$9b!8r3^wl4$rh8=yvgc-g%m@_hz7a-enn3u",
)
DEBUG = env_bool("DJANGO_DEBUG", True)

SITE_URL = os.getenv("SITE_URL", "https://bbccictfest.pro.bd").rstrip("/")
SITE_HOST = urlparse(SITE_URL).hostname or "bbccictfest.pro.bd"

if DEBUG:
    # ---------------- Development ----------------
    # Plain HTTP, open local hosts, console email.
    ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
    CSRF_TRUSTED_ORIGINS = env_list(
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000",
    )
else:
    # ---------------- Production ----------------
    # Closed hosts defaulting to the canonical domain, HTTPS enforced.
    ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", SITE_HOST)
    CSRF_TRUSTED_ORIGINS = env_list(
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        f"https://{SITE_HOST}",
    )

INSTALLED_APPS = [
    "jazzmin",  # must come before django.contrib.admin
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.sites",
    "pwa",
    "core",
    "accounts",
    "schools",
    "registrations",
    "volunteers",
    "blog",
]

SITE_ID = 1

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "bbccictfest_2026.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "bbccictfest_2026.wsgi.application"
ASGI_APPLICATION = "bbccictfest_2026.asgi.application"

DATABASES = _resolve_databases(
    os.getenv("DATABASE_URL", ""), os.getenv("SQLITE_NAME", "db.sqlite3"), BASE_DIR
)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "Asia/Dhaka")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Legacy folders shipped with the original static site (logo, game ROMs, emulator
# libs, old images). They are served as static assets so old URLs keep working
# while new uploads use URLField (external URLs) as required.
for _legacy in ("games", "images"):
    _p = BASE_DIR / _legacy
    if _p.is_dir() and _p not in STATICFILES_DIRS:
        STATICFILES_DIRS.append(_p)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # NOTE: plain compressed storage (no hashed manifest names) so the
    # arcade emulator/ROM libraries — which load sibling files by relative
    # path at runtime — keep working under /static/.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "core:home"

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@bbccictfest.pro.bd")

# ---------------------------------------------------------------- bKash (pybkash)
# Follows https://github.com/Itsmmdoha/pybkash + the dev.to tutorial:
# Token(username, password, app_key, app_secret, sandbox=...) then
# Client(token).create_payment(...) -> redirect bkash_url ->
# callback?paymentID=...&status=... -> execute_payment(payment_id).
BKASH_USERNAME = os.getenv("BKASH_USERNAME", "")
BKASH_PASSWORD = os.getenv("BKASH_PASSWORD", "")
BKASH_APP_KEY = os.getenv("BKASH_APP_KEY", "")
BKASH_APP_SECRET = os.getenv("BKASH_APP_SECRET", "")
BKASH_SANDBOX = env_bool("BKASH_SANDBOX", True)
BKASH_CALLBACK_BASE = os.getenv("BKASH_CALLBACK_BASE", SITE_URL).rstrip("/")
BKASH_ENABLED = bool(BKASH_USERNAME and BKASH_PASSWORD and BKASH_APP_KEY and BKASH_APP_SECRET)
# When credentials are absent (local dev) we run in MOCK mode so the full
# registration flow can be tested end-to-end without hitting bKash.
BKASH_MOCK = env_bool("BKASH_MOCK", not BKASH_ENABLED)

# ---------------------------------------------------------------- Jazzmin (ember theme, matches site design)
JAZZMIN_SETTINGS = {
    "site_title": "BBCC ICT Fest Admin",
    "site_header": "BBCC ICT Fest 2026",
    "site_brand": "BBCC ICT Fest",
    "site_logo": "img/logo.png",
    "login_logo": "img/logo.png",
    "site_logo_classes": "img-circle",
    "welcome_sign": "Welcome to BBCC ICT Fest 2026 control room",
    "copyright": "Bindubasini Boys' Computer Club",
    "search_model": ["auth.User", "blog.Post", "registrations.Registration"],
    "user_avatar": None,
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "order_with_respect_to": ["core", "schools", "registrations", "blog", "volunteers", "accounts", "auth"],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "core.SiteSetting": "fas fa-cogs",
        "core.Competition": "fas fa-trophy",
        "core.CommitteeMember": "fas fa-id-card",
        "core.Guest": "fas fa-star",
        "core.FAQ": "fas fa-question-circle",
        "core.Review": "fas fa-comments",
        "core.Game": "fas fa-gamepad",
        "registrations.Event": "fas fa-ticket-alt",
        "registrations.Registration": "fas fa-clipboard-list",
        "registrations.PaymentTransaction": "fas fa-money-bill-wave",
        "registrations.CampusAmbassadorApplication": "fas fa-flag",
        "schools.School": "fas fa-school",
        "volunteers.Volunteer": "fas fa-hands-helping",
        "blog.Post": "fas fa-blog",
        "blog.Comment": "fas fa-comment",
        "accounts.Profile": "fas fa-user-circle",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": True,
    "custom_css": "css/jazzmin-ember.css",
    "custom_js": None,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
}
JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": False,
    "accent": "accent-orange",
    "navbar": "navbar-dark",
    "no_navbar_border": True,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": True,
    "theme": "darkly",
    "dark_mode_theme": "darkly",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}

# ---------------------------------------------------------------- PWA (django-pwa)
PWA_APP_NAME = "BBCC ICT Fest 2026"
PWA_APP_DESCRIPTION = "Tangail's biggest ICT festival — quiz, science showdown, coding, chess & Rubik's cube."
PWA_APP_THEME_COLOR = "#0A0908"
PWA_APP_BACKGROUND_COLOR = "#0A0908"
PWA_APP_DISPLAY = "standalone"
PWA_APP_SCOPE = "/"
PWA_APP_ORIENTATION = "any"
PWA_APP_START_URL = "/"
PWA_APP_STATUS_BAR_COLOR = "black-translucent"
PWA_APP_ICONS = [
    {"src": "/static/img/logo-192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "/static/img/logo-512.png", "sizes": "512x512", "type": "image/png"},
]
PWA_APP_ICONS_APPLE = [{"src": "/static/img/logo-192.png", "sizes": "192x192"}]
PWA_APP_LANG = "en-US"
PWA_APP_DIR = "ltr"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if not DEBUG:
    # ---------------- Production hardening ----------------
    # Full setup: HTTPS redirect, secure cookies, HSTS. Behind a proxy that
    # terminates TLS, SECURE_PROXY_SSL_HEADER above keeps redirects correct.
    # Every knob below is env-overridable (see .env.example).
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
        "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True
    )
    SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)
    SECURE_REFERRER_POLICY = os.getenv(
        "DJANGO_SECURE_REFERRER_POLICY", "same-origin"
    )

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "registrations.bkash": {"handlers": ["console"], "level": "INFO"},
        "django.request": {"handlers": ["console"], "level": "WARNING"},
    },
}
