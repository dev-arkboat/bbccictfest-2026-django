from datetime import timedelta

from .models import Game, SiteSetting


def site_settings(request):
    """Expose CMS globals to every template.

    DB may not exist yet (first migrate) — fail soft to None/empty.
    """
    try:
        site = SiteSetting.get_solo()
    except Exception:
        site = None
    try:
        nav_games = list(Game.objects.filter(is_active=True))
    except Exception:
        nav_games = []
    site_event_end = None
    if site is not None and getattr(site, "event_date", None):
        try:
            site_event_end = site.event_date + timedelta(hours=8)
        except Exception:
            site_event_end = None
    return {"site": site, "nav_games": nav_games, "site_event_end": site_event_end}
