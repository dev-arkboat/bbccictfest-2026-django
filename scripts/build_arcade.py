"""Convert games/*.html into Django templates extending arcade/base.html.

- games/index.html  -> templates/arcade/index.html (cards become a {% for %} loop)
- games/<slug>.html -> templates/arcade/<slug>.html (head/body/scripts as blocks)
- <style> of index   -> static/css/arcade.css
- arcade-mobile.*    -> static/css|js/
- all relative asset URLs rewritten to {% static %} / {% url %} so the
  emulator + DOSBox + ROM libraries keep working under /games/<slug>/.
Run: uv run python scripts/build_arcade.py
"""

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAMES = ROOT / "games"
T = ROOT / "templates" / "arcade"
STATIC_CSS = ROOT / "static" / "css"
STATIC_JS = ROOT / "static" / "js"
SCRIPTS = Path(__file__).resolve().parent

VENDOR_PREFIX = re.compile(r"(?<!/|\w|-)(jsdos|emulatorjs|gb|gbc|gba|doom|doom2|heretic|quake|keen|wolf3d)/")
HTML_LINK = re.compile(r'href="([a-z0-9_]+\.html)(\?[^"]*)?"')


def rewrite_html_urls(snippet: str) -> str:
    s = snippet
    s = s.replace('href="arcade-mobile.css"', 'href="{% static \'css/arcade-mobile.css\' %}"')
    s = s.replace('src="arcade-mobile.js"', 'src="{% static \'js/arcade-mobile.js\' %}"')
    s = s.replace('src="../logo.png"', 'src="{% static \'img/logo.png\' %}"')
    s = s.replace('href="../logo.png"', 'href="{% static \'img/logo.png\' %}"')
    s = s.replace('href="../index.html"', 'href="{% url \'core:home\' %}"')
    s = s.replace('href="index.html"', 'href="{% url \'core:arcade\' %}"')

    def link_repl(m):
        page, query = m.group(1), m.group(2) or ""
        slug = page[:-5]
        return 'href="{%% url \'core:game_play\' \'%s\' %%}%s"' % (slug, query)

    s = HTML_LINK.sub(link_repl, s)
    s = VENDOR_PREFIX.sub(r"/static/\1/", s)
    return s


def rewrite_js(snippet: str, slug: str) -> str:
    s = VENDOR_PREFIX.sub(r"/static/\1/", snippet)
    if slug == "pokemon":
        # same-page query links (player boots from ?system=&rom=)
        s = s.replace("'pokemon.html?system='", "'?system='")
        s = s.replace('"pokemon.html?system="', '"?system="')
        s = re.sub(r"=\s*'pokemon\.html'", "= '?'", s)
        # ROM folders are concatenated at runtime (folder + '/' + file),
        # so point them at /static/ absolutely.
        for folder in ("gb", "gbc", "gba"):
            s = s.replace(f"folder: '{folder}'", f"folder: '/static/{folder}'")
    return s


# ---------------------------------------------------------------- index page
index_html = (GAMES / "index.html").read_text(encoding="utf-8")
style_m = re.search(r"<style>(.*?)</style>", index_html, re.DOTALL)
assert style_m
(STATIC_CSS / "arcade.css").write_text(style_m.group(1).strip() + "\n", encoding="utf-8")
shutil.copy(GAMES / "arcade-mobile.css", STATIC_CSS / "arcade-mobile.css")
shutil.copy(GAMES / "arcade-mobile.js", STATIC_JS / "arcade-mobile.js")

body = re.search(r"<body>(.*?)</body>", index_html, re.DOTALL).group(1)
hero = re.search(r'<section class="arcade-hero">.*?</section>', body, re.DOTALL).group(0)
cards = re.findall(r'<a href="([^"]+)" class="game-card"[^>]*>(.*?)</a>', body, flags=re.DOTALL)
assert len(cards) >= 20, len(cards)

seed_games = []
seen = set()
# Hub pages aggregate many variant cards (every "pokemon.html?system=…&rom=…"
# card points at the single pokemon hub). First-seen would keep a variant's
# title ("Pokémon Ruby"), so hub entries get explicit overrides.
HUB_OVERRIDES = {
    "pokemon": {
        "title": "Pokémon",
        "description": "All eleven official Pokémon games from the Game Boy era — Red, Blue, Yellow, Gold, Silver, Crystal, Ruby, Sapphire, Emerald, FireRed and LeafGreen.",
        "difficulty": "GB · GBC · GBA",
    },
}
for href, inner in cards:
    page = href.split("?")[0]
    assert page.endswith(".html"), href
    slug = page[:-5]
    icon = re.search(r'<div class="game-ico (g-\d+)">\s*(<svg.*?</svg>)\s*</div>', inner, re.DOTALL)
    title = re.search(r"<h3>(.*?)</h3>", inner, re.DOTALL).group(1).strip()
    desc = re.search(r"<p>(.*?)</p>", inner, re.DOTALL).group(1).strip()
    diff = re.search(r'<span class="game-diff">(.*?)</span>', inner)
    color = re.search(r"background:(#[0-9A-Fa-f]{3,8})", inner)
    if slug in seen:
        continue
    seen.add(slug)
    seed_games.append({
        "title": title, "slug": slug, "description": desc,
        "difficulty": diff.group(1).strip() if diff else "Arcade",
        "icon_svg": icon.group(2) if icon else "",
        "icon_class": icon.group(1) if icon else "g-1",
        "accent_color": color.group(1) if color else "#FF7A1A",
    })

for g in seed_games:
    if g["slug"] in HUB_OVERRIDES:
        g.update(HUB_OVERRIDES[g["slug"]])

seed_path = SCRIPTS / "seed_data.json"
seed = json.loads(seed_path.read_text(encoding="utf-8"))
seed["games"] = seed_games
seed_path.write_text(json.dumps(seed, indent=2, ensure_ascii=False), encoding="utf-8")
print("seed games:", len(seed_games))

# ---------------------------------------------------------------- arcade/base.html
(T / "").mkdir(parents=True, exist_ok=True)
(T / "base.html").write_text("""{% extends "base.html" %}
{% load static %}

{% block extra_css %}
<link rel="stylesheet" href="{% static 'css/arcade.css' %}">
<link rel="stylesheet" href="{% static 'css/arcade-mobile.css' %}">
{% block arcade_css %}{% endblock %}
{% endblock %}

{% block nav %}
  <nav class="arcade-nav" aria-label="Arcade navigation">
    <div class="container arcade-nav-inner">
      <a href="{% url 'core:home' %}" class="arcade-logo">
        <img src="{% static 'img/logo.png' %}" alt="BBCC ICT Fest logo">
        BBCC Arcade
      </a>
      <div class="arcade-links" style="display:flex;gap:8px;">
        <a href="{% url 'core:home' %}" aria-label="Back to festival" class="arcade-back"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>Back to Fest</a>
        <a href="{% url 'core:arcade' %}" aria-label="All games" class="arcade-back"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="10" r="1.5"/><circle cx="15" cy="10" r="1.5"/><path d="m6.5 16 2-2 2 2 2-2 2 2"/></svg>Arcade</a>
      </div>
    </div>
  </nav>
{% endblock nav %}

{% block content %}
{% block game_bar %}{% endblock %}
{% block arcade_content %}{% endblock %}
{% endblock %}

{% block footer %}
  <footer class="arcade-foot">
    <div class="container">
      <p>BBCC Arcade &copy; 2026 — part of <b>BBCC ICT Fest</b> | <a href="{% url 'core:home' %}" style="color:var(--text-2);">Back to the Fest</a></p>
    </div>
  </footer>
{% endblock footer %}

{% block extra_js %}
<script src="{% static 'js/arcade-mobile.js' %}"></script>
{% block arcade_js %}{% endblock %}
{% endblock %}
""", encoding="utf-8")

# ---------------------------------------------------------------- arcade/index.html
hero = hero.replace('src="../logo.png"', 'src="{% static \'img/logo.png\' %}"')
(T / "index.html").write_text("""{% extends "arcade/base.html" %}
{% load static %}

{% block title %}BBCC Arcade — Free Browser Games | BBCC ICT Fest 2026{% endblock %}
{% block meta_description %}<meta name="description" content="Play free browser games — Snake, Tetris, 2048, Flappy Bird, Pong, Breakout, Memory, Minesweeper, Doom and classic Pokémon games — on the BBCC Arcade.">{% endblock %}

{% block arcade_content %}
""" + hero + """
  <section class="game-grid">
    <div class="container game-grid-inner">
      {% for game in games %}
      <a href="{{ game.get_absolute_url }}" class="game-card" data-card>
        <div class="game-ico {{ game.icon_class }}">
          {{ game.icon_svg|safe }}
        </div>
        <h3>{{ game.title }}</h3>
        <p>{{ game.description }}</p>
        <div class="game-meta">
          <span class="game-diff">{{ game.difficulty }}</span>
          <span class="game-play">Play <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg></span>
        </div>
      </a>
      {% endfor %}
    </div>
  </section>
{% endblock %}
""", encoding="utf-8")

# ---------------------------------------------------------------- per-game pages
GAME_BAR = """{% block game_bar %}
  <div class="game-bar" aria-label="Game switcher">
    <div class="container game-bar-inner">
      {% for g in games %}
      <a href="{{ g.get_absolute_url }}"{% if g.slug == game.slug %} class="on"{% endif %}>{{ g.title }}</a>
      {% endfor %}
    </div>
  </div>
{% endblock %}
"""

files = sorted(GAMES.glob("*.html"))
assert len(files) == 16, [f.name for f in files]
for path in files:
    if path.name == "index.html":
        continue
    slug = path.stem
    raw = path.read_text(encoding="utf-8")
    title = re.search(r"<title>(.*?)</title>", raw, re.DOTALL).group(1).strip()
    desc_m = re.search(r'<meta name="description" content="(.*?)"', raw)
    desc = desc_m.group(1) if desc_m else title
    page_style = re.search(r"<style>(.*?)</style>", raw, re.DOTALL).group(1)
    page_body = re.search(r"<body>(.*?)</body>", raw, re.DOTALL).group(1)

    # strip shared chrome (provided by arcade/base.html)
    page_body = re.sub(r'<nav class="arcade-nav".*?</nav>', "", page_body, flags=re.DOTALL)
    page_body = re.sub(r'<div class="game-bar".*?</div>\s*</div>', "", page_body, flags=re.DOTALL)
    page_body = re.sub(r'<footer class="game-foot".*?</footer>', "", page_body, flags=re.DOTALL)
    # scripts live in the arcade_js block (collected below) — drop from body
    page_body = re.sub(r"<script[^>]*>.*?</script>", "", page_body, flags=re.DOTALL)

    # split game-head vs rest of .container
    head_m = re.search(r'<div class="game-head">.*?</div>\s*</div>', page_body, flags=re.DOTALL)
    # game-head contains nested divs (game-tag); use balanced scan instead
    hi = page_body.find('<div class="game-head">')
    if hi != -1:
        depth = 0
        end = None
        for m in re.finditer(r"</?div\b[^>]*>", page_body[hi:]):
            tag = m.group(0)
            depth += -1 if tag.startswith("</") else 1
            if depth == 0:
                end = hi + m.end()
                break
        assert end, slug
        game_head, game_rest = page_body[hi:end], page_body[:hi] + page_body[end:]
    else:
        game_head, game_rest = "", page_body

    # scripts: keep lib srcs + inline bodies, rewrite urls
    scripts_out = []
    for sm in re.finditer(r"<script([^>]*)>(.*?)</script>", raw, flags=re.DOTALL):
        attrs, body_js = sm.group(1), sm.group(2)
        src_m = re.search(r'src="([^"]+)"', attrs)
        if src_m:
            src = src_m.group(1)
            if src in ("arcade-mobile.js", "arcade-mobile.css"):
                continue  # provided by arcade/base.html
            if src.startswith(("http", "//")):
                scripts_out.append(f'<script src="{src}"></script>')
            else:
                assert not src.startswith("../"), (slug, src)
                scripts_out.append('<script src="{%% static \'%s\' %%}"></script>' % src)
        else:
            scripts_out.append("<script>\n%s\n  </script>" % rewrite_js(body_js, slug))

    # report any leftover suspicious relative refs
    for pat in re.findall(r'(?:src|href)="(?!\{|https?://|#|data:)([^"]+)"', game_head + game_rest):
        if pat.startswith("/static/"):
            continue
        print(f"WARN {slug}: unhandled ref {pat}")

    tpl = ("{%% extends \"arcade/base.html\" %%}\n{%% load static %%}\n\n"
           "{%% block title %%}%s{%% endblock %%}\n"
           "{%% block meta_description %%}<meta name=\"description\" content=\"%s\">{%% endblock %%}\n"
           "{%% block canonical %%}<link rel=\"canonical\" href=\"https://bbccictfest.pro.bd/games/%s/\">{%% endblock %%}\n"
           "{%% block arcade_css %%}<style>\n%s\n</style>\n{%% endblock %%}\n\n"
           "%s\n\n"
           "{%% block arcade_content %%}\n"
           "  <main class=\"game-wrap\">\n"
           "    <div class=\"container\">\n%s\n%s\n"
           "    </div>\n"
           "  </main>\n"
           "{%% endblock %%}\n\n"
           "{%% block arcade_js %%}\n%s\n{%% endblock %%}\n")
    page = tpl % (title, desc.replace('"', "&quot;"), slug, page_style.strip(),
                  GAME_BAR, rewrite_html_urls(game_head), rewrite_html_urls(game_rest),
                  "\n".join(scripts_out))
    (T / f"{slug}.html").write_text(page, encoding="utf-8")
    print("wrote", slug)

print("arcade templates done:", sorted(p.stem for p in T.glob("*.html") if p.stem not in ("base", "index")))
