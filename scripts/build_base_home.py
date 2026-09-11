"""Build base.html + home.html + main.css + main.js from the legacy index.html.

Design is preserved exactly: CSS/JS are moved verbatim to static files with
only the minimal hooks needed for Django (data-attributes, guards, URL tags).
Run: uv run python scripts/build_base_home.py
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "index.html"
TEMPLATES = ROOT / "templates"
STATIC_CSS = ROOT / "static" / "css"
STATIC_JS = ROOT / "static" / "js"
SCRIPTS = Path(__file__).resolve().parent

GOOGLE_MAIN = "https://docs.google.com/forms/d/e/1FAIpQLSe90Cy1MTDmK48VDCAx9Y3JR0B9gO1Bkhvk91G41wxKxM4Vsg/viewform?usp=header"
GOOGLE_CA = "https://docs.google.com/forms/d/e/1FAIpQLSchcKKNp8awB4aq6P7Fq1kiJ7QE_7bXH5Z2hzMm97FSRkIXkQ/viewform"

html = SRC.read_text(encoding="utf-8")

# ---------------------------------------------------------------- helpers

def balanced_div(source: str, start: int):
    """Return (block, end) for the <div ...> at `start` incl. nested divs."""
    assert source.startswith("<div", start), source[start:start + 60]
    depth = 0
    pos = start
    tag_re = re.compile(r"</?div\b[^>]*>", re.IGNORECASE)
    for m in tag_re.finditer(source, start):
        if m.group(0).startswith("</"):
            depth -= 1
        else:
            depth += 1
        if depth == 0:
            return source[start:m.end()], m.end()
    raise ValueError("unbalanced div at %d" % start)


def extract_cards(source, marker):
    out = []
    idx = 0
    while True:
        i = source.find(marker, idx)
        if i == -1:
            return out
        block, end = balanced_div(source, i)
        out.append(block)
        idx = end


def strip_google_links(snippet: str) -> str:
    """Rewrite legacy Google-Form anchors to internal URLs, drop target/rel."""

    def repl(m):
        attrs, href, tail = m.group(1), m.group(2), m.group(3)
        new_href = "{% url 'registrations:ca_apply' %}" if "SchcKKNp8" in href else "{% url 'registrations:events' %}"
        merged = (attrs + " " + tail).replace('target="_blank"', "").replace("rel=\"noopener\"", "")
        merged = re.sub(r"\s+", " ", merged).strip()
        return f"<a href=\"{new_href}\" {merged}>" if merged else f"<a href=\"{new_href}\">"

    return re.sub(r"<a\b([^<>]*?)href=\"(https://docs\.google\.com[^\"]*)\"([^<>]*?)>", repl, snippet)


# ---------------------------------------------------------------- 1. CSS / JS
style_m = re.search(r"<style>(.*?)</style>", html, re.DOTALL)
assert style_m, "no <style> found"
main_css = style_m.group(1).strip() + "\n"
main_css += """
/* ---------- Django additions (same ember design language) ---------- */
.django-messages { display: flex; flex-direction: column; gap: 10px; padding: 18px 0 0; }
.django-message { padding: 13px 20px; border-radius: 12px; font-size: 14px; border: 1px solid var(--line-2); background: var(--card); color: var(--text); }
.django-message.success { border-color: var(--ember-line); background: var(--ember-soft); }
.django-message.error { border-color: rgba(226,38,14,.4); background: rgba(226,38,14,.08); }
.django-message.info { border-color: rgba(94,185,255,.35); background: rgba(94,185,255,.07); }
.form-wrap { max-width: 640px; margin: 0 auto; }
.form-grid { display: grid; gap: 16px; }
.form-field label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 7px; color: var(--text-2); }
.form-input, .form-field input, .form-field textarea, .form-field select { width: 100%; padding: 13px 16px; border-radius: 12px; background: var(--card); border: 1px solid var(--line-2); color: var(--text); font-family: var(--font-body); font-size: 14.5px; transition: border-color .3s ease, box-shadow .3s ease; }
.form-input:focus, .form-field input:focus, .form-field textarea:focus, .form-field select:focus { outline: none; border-color: var(--ember-line); box-shadow: 0 0 0 4px rgba(255,122,26,.12); }
.form-errors, .errorlist { list-style: none; font-size: 13px; color: #FF8A7A; margin: 6px 0 0; padding: 0; }
.page-hero { padding: calc(var(--nav-h) + clamp(48px,7vw,88px)) 0 clamp(28px,4vw,44px); text-align: center; position: relative; }
.page-hero::before { content: ''; position: absolute; inset: 0; background: radial-gradient(ellipse 60% 50% at 50% 0%, rgba(255,122,26,.09) 0%, transparent 60%); pointer-events: none; }
.auth-links { display: inline-flex; gap: 8px; align-items: center; }
.stars { color: var(--gold); letter-spacing: 3px; font-size: 15px; }
.review-card { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius-lg); padding: 26px; display: flex; flex-direction: column; gap: 12px; transition: border-color .35s ease, transform .4s var(--ease-out); }
.review-card:hover { border-color: var(--ember-line); transform: translateY(-4px); }
.review-card p { font-size: 14px; color: var(--text-2); line-height: 1.75; flex-grow: 1; }
.review-who { display: flex; align-items: center; gap: 12px; }
.review-ava { width: 42px; height: 42px; border-radius: 50%; background: var(--ember-soft); border: 1px solid var(--ember-line); display: flex; align-items: center; justify-content: center; font-family: var(--font-display); font-weight: 700; font-size: 15px; color: var(--ember); overflow: hidden; flex-shrink: 0; }
.review-ava img { width: 100%; height: 100%; object-fit: cover; }
.review-who b { display: block; font-size: 14px; }
.review-who span { font-size: 12px; color: var(--text-3); font-family: var(--font-mono); }
.reviews-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
@media (max-width: 900px) { .reviews-grid { grid-template-columns: 1fr; max-width: 520px; margin: 0 auto; } }
.blog-cover { width: 100%; height: 180px; object-fit: cover; border-radius: 12px; border: 1px solid var(--line); }
.blog-meta { font-family: var(--font-mono); font-size: 11px; color: var(--text-3); letter-spacing: 1px; }
.like-btn { background: var(--ember-soft); border: 1px solid var(--ember-line); color: var(--ember); border-radius: 100px; padding: 9px 22px; font-family: var(--font-body); font-size: 13.5px; font-weight: 600; cursor: pointer; transition: all .3s var(--ease-out); }
.like-btn:hover { transform: translateY(-2px); box-shadow: 0 10px 26px -12px rgba(255,122,26,.6); }
.like-btn.liked { background: var(--grad); color: #1A0D02; }
.comment-card { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius-md); padding: 18px 20px; }
.comment-card p { font-size: 14px; color: var(--text-2); }
.kv { display: grid; grid-template-columns: 180px 1fr; gap: 10px 18px; font-size: 14px; }
.kv dt { color: var(--text-3); font-family: var(--font-mono); font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }
.kv dd { margin: 0; color: var(--text); }
.status-pill { display: inline-block; padding: 5px 16px; border-radius: 100px; font-family: var(--font-mono); font-size: 11px; letter-spacing: 1px; text-transform: uppercase; border: 1px solid var(--line-2); }
.status-paid, .status-confirmed { background: rgba(74,222,128,.1); border-color: rgba(74,222,128,.35); color: #4ADE80; }
.status-payment_pending, .status-pending { background: var(--ember-soft); border-color: var(--ember-line); color: var(--ember); }
.status-cancelled, .status-failed { background: rgba(226,38,14,.1); border-color: rgba(226,38,14,.35); color: #FF8A7A; }
.table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: var(--radius-md); }
table.fest-table { width: 100%; border-collapse: collapse; font-size: 13.5px; min-width: 640px; }
.fest-table th { text-align: left; font-family: var(--font-mono); font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: var(--text-3); padding: 13px 16px; border-bottom: 1px solid var(--line); background: var(--bg-2); }
.fest-table td { padding: 13px 16px; border-bottom: 1px solid var(--line); color: var(--text-2); }
.fest-table tr:last-child td { border-bottom: none; }
.fest-table a { color: var(--ember); }
"""
(STATIC_CSS).mkdir(parents=True, exist_ok=True)
(STATIC_CSS / "main.css").write_text(main_css, encoding="utf-8")

scripts = re.findall(r"<script(?![^>]*ld\+json)([^>]*)>(.*?)</script>", html, re.DOTALL)
inline_js = [body for attrs, body in scripts if "src=" not in attrs]
assert len(inline_js) == 1, f"expected 1 inline script, got {len(inline_js)}"
js = inline_js[0]

# -- countdown target from data attribute, guarded when absent --
js = js.replace(
    "const TARGET = new Date('2026-09-19T09:00:00+06:00');",
    "const __cdEl = document.getElementById('countdown');\n"
    "    const TARGET = new Date((__cdEl && __cdEl.dataset.target) || '2026-09-19T09:00:00+06:00');",
)
# -- hero subtitle from data attribute --
m_sub = re.search(r"const subText = \".*?\";", js)
assert m_sub, "subText line not found"
js = js.replace(
    m_sub.group(0),
    "const __subEl = document.getElementById('heroSub');\n"
    "      const subText = (__subEl && __subEl.dataset.subtext) || \"Tangail's biggest technology festival.\";",
)
# -- guard hero entrance when #heroSub missing (non-home pages) --
js = js.replace(
    "heroIntro.eventCallback('onStart', function () { typewrite(sub, subText, 14); });",
    "heroIntro.eventCallback('onStart', function () { if (sub) typewrite(sub, subText, 14); });",
)
js = js.replace("      } else {\n        sub.textContent = subText;\n      }",
                "      } else if (sub) {\n        sub.textContent = subText;\n      }")
# -- scrollspy works with /#section hrefs too --
js = js.replace(
    "l.classList.toggle('active', l.getAttribute('href') === '#' + id);",
    "l.classList.toggle('active', (l.getAttribute('href') || '').endsWith('#' + id));",
)
# -- drop dead registration-modal JS (no triggers; custom form replaces it) --
# NOTE: the modal block is top-level and runs to end-of-script (it is NOT
# inside the DOMContentLoaded handler, which already closed above), so drop
# everything from the marker to EOF and keep only the Escape-key handler.
start = js.find("/* modal */")
assert start != -1
modal_block = js[start:]
assert "showRegModal" in modal_block and "navLinks" in modal_block
keydown_keep = """
    /* modal removed: registrations use the built-in form (registrations:events) */
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        var navLinksEl = document.getElementById('navLinks');
        if (navLinksEl && navLinksEl.classList.contains('open')) {
          navLinksEl.classList.remove('open');
          document.getElementById('navToggle').setAttribute('aria-expanded', 'false');
          document.body.style.overflow = '';
        }
      }
    });
"""
js = js[:start] + keydown_keep
assert "regModal" not in js and "showRegModal" not in js

# -- guard countdown when absent (non-home pages) --
c_start = js.find("/* countdown */")
f_start = js.find("/* faq */", c_start)
assert c_start != -1 and f_start != -1
countdown_block = js[c_start:f_start]
guarded = "/* countdown */\n    if (document.getElementById('cDays')) {\n"
for line in countdown_block.splitlines()[1:]:
    if line.strip():
        guarded += "  " + line + "\n"
guarded += "    }\n\n"
js = js[:c_start] + guarded + js[f_start:]
(STATIC_JS).mkdir(parents=True, exist_ok=True)
(STATIC_JS / "main.js").write_text(js.strip() + "\n", encoding="utf-8")

# ---------------------------------------------------------------- 2. HEAD
head = re.search(r"<head>(.*?)</head>", html, re.DOTALL).group(1)
orig_title = re.search(r"<title>(.*?)</title>", head, re.DOTALL).group(1)
orig_desc = re.search(r'<meta name="description" content="(.*?)"', head).group(1)

# NOTE: keep the <title> tags OUTSIDE the block — children override with
# plain text, and a bare block would leak the title as visible page text.
head = head.replace(f"<title>{orig_title}</title>",
                    f"<title>{{% block title %}}{orig_title}{{% endblock %}}</title>")
head = head.replace(f'<meta name="description" content="{orig_desc}"',
                    '{% block meta_description %}<meta name="description" content="{{ site.meta_description|default:"'
                    + orig_desc + '" }}">{% endblock %}',
                    1)
head = re.sub(r'<link rel="canonical" href="[^"]*">',
              '{% block canonical %}<link rel="canonical" href="https://bbccictfest.pro.bd{{ request.path }}">{% endblock %}',
              head, count=1)
head = head.replace('<link rel="icon" type="image/png" href="logo.png">',
                    '<link rel="icon" type="image/png" href="{% static \'img/logo.png\' %}">')
# dynamic event dates in JSON-LD
head = head.replace('"startDate": "2026-09-19T09:00:00+06:00"',
                    '"startDate": "{{ site.event_date|date:\'c\'|default:\'2026-09-19T09:00:00+06:00\' }}"')
head = head.replace('"endDate": "2026-09-19T17:00:00+06:00"',
                    '"endDate": "{{ site_event_end|date:\'c\'|default:\'2026-09-19T17:00:00+06:00\' }}"')
# swap style block for static css
head = re.sub(r"<style>.*?</style>", "{% static_css %}", head, flags=re.DOTALL)
head = head.replace("{% static_css %}",
                    '<link rel="stylesheet" href="{% static \'css/main.css\' %}">\n'
                    "  {% block extra_css %}{% endblock %}")
head += "\n  {% progressive_web_app_meta %}\n  {% block extra_head %}{% endblock %}"

# ---------------------------------------------------------------- 3. NAV
nav_games_loop = """<li class="nav-games" id="navGames">
          <a href="{% url 'core:arcade' %}" class="nav-link" aria-haspopup="true" aria-expanded="false">
            Games
            <svg class="caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:12px;height:12px;"><path d="m6 9 6 6 6-6"/></svg>
          </a>
          <div class="nav-dropdown" role="menu">
            {% for g in nav_games %}
            <a href="{{ g.get_absolute_url }}" role="menuitem"><span class="bd" style="background:{{ g.accent_color }};"></span><span><b>{{ g.title }}</b><span>{{ g.difficulty }}</span></span></a>
            {% endfor %}
          </div>
        </li>"""
nav_old = re.search(r'<nav class="nav".*?</nav>', html, re.DOTALL).group(0)
# section anchors -> home-anchored urls
nav_new = nav_old
nav_new = re.sub(r'href="#(about|competitions|timeline|guests|committee|campus-ambassador|faq|top|register)"',
                 "href=\"{% url 'core:home' %}#\\1\"", nav_new)
nav_new = nav_new.replace('<img src="logo.png"', '<img src="{% static \'img/logo.png\' %}"')
# swap games dropdown
nav_new = re.sub(r'<li class="nav-games".*?</li>\s*(?=<li><a href="https://docs)',
                 nav_games_loop + "\n        ", nav_new, flags=re.DOTALL)
# register button + auth links
nav_new = strip_google_links(nav_new)
auth_li = """<li class="nav-games">{% if user.is_authenticated %}<a href="{% url 'accounts:profile' %}" class="nav-link">👤 {{ user.username }}</a>{% else %}<a href="{% url 'accounts:login' %}" class="nav-link">Login</a>{% endif %}</li>"""
nav_new = nav_new.replace("</ul>", "        " + auth_li + "\n      </ul>")
assert "docs.google.com" not in nav_new
assert "logo.png" not in nav_new or "static" in nav_new

# ---------------------------------------------------------------- 4. MAIN -> HOME CONTENT
main_inner = re.search(r'<main id="top">(.*?)</main>', html, re.DOTALL).group(1)
assert '<div class="modal-overlay"' not in main_inner  # modal lives outside main
home = main_inner

# hero chips -> loop
home = re.sub(r'<div class="hero-chip chip-\d+">.*?</div>',
              '<div class="hero-chip chip-{{ forloop.counter }}">{% safe_chip %}</div>', home, flags=re.DOTALL)
# build chip loop around them: find the 4 consecutive placeholders
chip_ph = '<div class="hero-chip chip-{{ forloop.counter }}">{% safe_chip %}</div>'
assert home.count(chip_ph) == 4, home.count(chip_ph)
home = home.replace(
    "      " + chip_ph + "\n" + "      " + chip_ph + "\n" + "      " + chip_ph + "\n" + "      " + chip_ph,
    "      {% for chip in chips %}\n      <div class=\"hero-chip chip-{{ forloop.counter }}\">{{ chip.html|safe }}</div>\n      {% endfor %}",
)
# hero kicker
home = re.sub(r'(<div class="hero-label" data-hero-fade>\s*<span class="hero-label-dot"></span>\s*).*?(\s*</div>)',
              r"\1{{ site.hero_kicker|default:'Registrations are Open' }}\2", home, flags=re.DOTALL)
# hero title
home = home.replace('<span class="line-inner" data-hero-line>ICT FEST</span>',
                    '<span class="line-inner" data-hero-line>{{ site.hero_title_line1|default:"ICT FEST" }}</span>')
home = home.replace('<span class="line-inner gradient-text" data-hero-line>2026<span class="hero-cursor" aria-hidden="true"></span></span>',
                    '<span class="line-inner gradient-text" data-hero-line>{{ site.hero_title_line2|default:"2026" }}<span class="hero-cursor" aria-hidden="true"></span></span>')
# hero sub
home = home.replace('<p class="hero-sub" id="heroSub" data-hero-fade></p>',
                    '<p class="hero-sub" id="heroSub" data-hero-fade data-subtext="{{ site.hero_subtitle|escapejs }}"></p>')
# hero meta texts
home = home.replace("September 19, 2026", "{{ site.event_date|date:'F j, Y' }}")
home = home.replace("Bindubasini Boys' School, Tangail", "{{ site.venue_name }}")
home = home.replace("1000+ Participants", "{{ site.participants_label }}")
# hero actions register -> internal
home = strip_google_links(home)
home = home.replace('<a href="{% url \'registrations:events\' %}"  class="btn btn-primary" data-magnetic>',
                    '<a href="{% url \'registrations:events\' %}" class="btn btn-primary" data-magnetic>')
# countdown target
home = home.replace('<div class="countdown" id="countdown" data-hero-group>',
                    '<div class="countdown" id="countdown" data-hero-group data-target="{{ site.event_date|date:\'c\' }}">')
# ticker halves -> loop
ticker_half_re = re.compile(r'<div class="ticker-half">.*?</div>', re.DOTALL)
halves = ticker_half_re.findall(home)
assert len(halves) == 2
ticker_loop = ('<div class="ticker-half">\n'
               '          {% for item in ticker_items %}<span class="ticker-item">{{ item.html|safe }}</span><span class="ticker-star">✦</span>{% endfor %}\n'
               '        </div>')
home = ticker_half_re.sub(ticker_loop, home)

# ---- about ----
home = home.replace("The Biggest ICT Event<br><span class=\"gradient-text\">In the History of Tangail District</span>",
                    "{{ site.about_heading_a }}<br><span class=\"gradient-text\">{{ site.about_heading_b }}</span>")
paras = re.findall(r'<div class="about-text" data-reveal>\s*<p>.*?</p>\s*<p>.*?</p>', home, flags=re.DOTALL)
assert len(paras) == 1
home = re.sub(r'(<div class="about-text" data-reveal>\s*)<p>.*?</p>\s*<p>.*?</p>',
              r"\1<p>{{ site.about_para1 }}</p>\n            <p>{{ site.about_para2 }}</p>", home, flags=re.DOTALL, count=1)
# stats: drop 4 hardcoded, add loop
stat_re = re.compile(r'<div class="about-stat"><div class="about-stat-num"><span data-count="\d+">0</span>(.*?)</div><div class="about-stat-label">.*?</div></div>', re.DOTALL)
assert len(stat_re.findall(home)) == 4
home = stat_re.sub("", home)
home = home.replace('<div class="about-stats" data-reveal>',
                    '<div class="about-stats" data-reveal>\n'
                    '            {% for stat in stats %}<div class="about-stat"><div class="about-stat-num"><span data-count="{{ stat.value }}">0</span>{{ stat.suffix }}</div><div class="about-stat-label">{{ stat.label }}</div></div>{% endfor %}')

# ---- competitions (balanced extract -> loop) ----
comp_grid_start = home.find('<div class="comp-grid">')
assert comp_grid_start != -1
# find end: the comp-grid closes right before "</div>\n      </div>\n    </section>" of competitions; use balanced extract
grid_block, grid_end = balanced_div(home, comp_grid_start)
cards = extract_cards(grid_block, '<div class="comp-card"')
assert len(cards) == 5, len(cards)
seed_competitions = []
for card in cards:
    title = re.search(r"<h3>(.*?)</h3>", card, re.DOTALL).group(1).strip()
    desc = re.search(r'<p class="comp-desc">(.*?)</p>', card, re.DOTALL).group(1).strip()
    icon = re.search(r'<div class="comp-icon (comp-icon-\d+)">\s*(<svg.*?</svg>)\s*</div>', card, re.DOTALL)
    icon_class, icon_svg = (icon.group(1), icon.group(2)) if icon else ("comp-icon-1", "")
    tags = [(t, "comp-tag-highlight" in t_full) for t_full, t in
            [(m.group(0), m.group(1).strip()) for m in re.finditer(r'<span class="comp-tag([^"]*)">(.*?)</span>', card, re.DOTALL)]]
    details = [m.group(1).strip() for m in re.finditer(r'<div class="comp-detail">\s*<svg.*?</svg>\s*<span>(.*?)</span>', card, re.DOTALL)]
    seed_competitions.append({"title": title, "description": desc, "icon_class": icon_class,
                              "icon_svg": icon_svg, "tags": tags, "details": details})
comp_loop = ('<div class="comp-grid">\n'
             '          {% for comp in competitions %}\n'
             '          <div class="comp-card" data-reveal>\n'
             '            <div class="comp-icon {{ comp.icon_class }}">\n'
             '              {{ comp.icon_svg|safe }}\n'
             '            </div>\n'
             '            <h3>{{ comp.title }}</h3>\n'
             '            <p class="comp-desc">{{ comp.description }}</p>\n'
             '            <div class="comp-tags">\n'
             '              {% for tag in comp.tags.all %}<span class="comp-tag{% if tag.highlight %} comp-tag-highlight{% endif %}">{{ tag.text }}</span>{% endfor %}\n'
             '            </div>\n'
             '            <div class="comp-details">\n'
             '              {% for d in comp.details.all %}\n'
             '              <div class="comp-detail">\n'
             '                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>\n'
             '                <span>{{ d.text }}</span>\n'
             '              </div>\n'
             '              {% endfor %}\n'
             '            </div>\n'
             '          </div>\n'
             '          {% endfor %}\n'
             '        </div>')
home = home[:comp_grid_start] + comp_loop + home[grid_end:]

# ---- timeline ----
tl_items = extract_cards(home, '<div class="tl-item"')
assert len(tl_items) == 4, len(tl_items)
seed_timeline = []
for item in tl_items:
    no = re.search(r'<div class="tl-dot (tl-dot-\d+)">(\d+)</div>', item)
    tag = re.search(r'<span class="tl-step-tag">(.*?)</span>', item).group(1)
    title = re.search(r"<h4>(.*?)</h4>", item).group(1)
    text = re.search(r"<p>(.*?)</p>", item, re.DOTALL).group(1)
    seed_timeline.append({"dot": no.group(1), "no": no.group(2), "tag": tag, "title": title, "text": text})
first_tl = home.find('<div class="tl-item"')
last_block, last_end = balanced_div(home, home.rfind('<div class="tl-item"'))
tl_loop = ('{% for step in timeline %}\n'
           '          <div class="tl-item" data-reveal>\n'
           '            <div class="tl-dot {{ step.dot_class }}">{{ step.step_no }}</div>\n'
           '            <div class="tl-content">\n'
           '              <span class="tl-step-tag">{{ step.tag }}</span>\n'
           '              <h4>{{ step.title }}</h4>\n'
           '              <p>{{ step.text }}</p>\n'
           '            </div>\n'
           '          </div>\n'
           '          {% endfor %}')
home = home[:first_tl] + tl_loop + home[last_end:]

print("seed competitions:", len(seed_competitions), "| timeline:", len(seed_timeline))
(SCRIPTS / "_parsed_home.txt").write_text(
    "COMP_CARDS=%d TL=%d" % (len(cards), len(tl_items)), encoding="utf-8")

# ---- guests ----
guest_cards = extract_cards(home, '<div class="guest-card')
assert len(guest_cards) == 3, len(guest_cards)
seed_guests = []
for card in guest_cards:
    featured = "featured" in card.split('data-reveal')[0]
    role = re.search(r'<div class="guest-role">(.*?)</div>', card).group(1)
    name = re.search(r"<h4>(.*?)</h4>", card).group(1)
    bio = re.search(r'<p class="guest-bio">(.*?)</p>', card, re.DOTALL).group(1)
    img = re.search(r'<img class="avatar-img"[^>]*src="([^"]+)"', card)
    av = re.search(r'<div class="guest-avatar (g-a\d)">', card)
    seed_guests.append({"name": name, "role": role, "bio": bio,
                        "image": img.group(1) if img else "",
                        "avatar_class": av.group(1) if av else "g-a1",
                        "featured": featured})
g_first = home.find('<div class="guest-card')
g_last, g_end = balanced_div(home, home.rfind('<div class="guest-card'))
guest_loop = ('{% for guest in guests %}\n'
              '          <div class="guest-card{% if guest.is_featured %} featured{% endif %}" data-reveal data-tilt>\n'
              '            {% if guest.is_featured %}<span class="guest-ribbon">{{ guest.role }}</span>{% endif %}\n'
              '            <div class="guest-avatar {{ guest.avatar_class }}">{% if guest.image_url %}<img class="avatar-img" loading="lazy" decoding="async" width="84" height="84" src="{{ guest.image_url }}" alt="{{ guest.name }}" onerror="this.remove()">{% endif %}{{ guest.initials }}</div>\n'
              '            <h4>{{ guest.name }}</h4>\n'
              '            <div class="guest-role">{{ guest.role }}</div>\n'
              '            <p class="guest-bio">{{ guest.bio }}</p>\n'
              '          </div>\n'
              '          {% endfor %}')
home = home[:g_first] + guest_loop + home[g_end:]

# ---- committee (subhead + grid pairs) ----
seed_committee = []
cat_pat = re.compile(r'<div class="committee-subhead" data-reveal>(.*?)</div>\s*<div class="committee-grid">', re.DOTALL)
cat_names = [m.group(1).strip() for m in cat_pat.finditer(home)]
grids = extract_cards(home, '<div class="committee-grid">')
assert len(cat_names) == len(grids), (len(cat_names), len(grids))
# replace from first subhead to end of last grid with loop
c_first = home.find('<div class="committee-subhead"')
c_last_start = home.rfind('<div class="committee-grid">')
_, c_end = balanced_div(home, c_last_start)
for name, grid in zip(cat_names, grids):
    members = []
    for card in extract_cards(grid, '<div class="member-card"'):
        mname = re.search(r"<h4>(.*?)</h4>", card, re.DOTALL).group(1).strip()
        mrole = re.search(r'<div class="member-role">(.*?)</div>', card, re.DOTALL).group(1).strip()
        mimg = re.search(r'<img class="avatar-img"[^>]*src="([^"]+)"', card)
        members.append({"name": mname, "role": mrole, "image": mimg.group(1) if mimg else ""})
    seed_committee.append({"name": name, "members": members})
committee_loop = ('{% for category in committee_categories %}\n'
                  '        <div class="committee-subhead" data-reveal>{{ category.name }}</div>\n'
                  '        <div class="committee-grid">\n'
                  '          {% for member in category.members.all %}\n'
                  '          <div class="member-card" data-reveal>\n'
                  '            <div class="member-photo">{% if member.image_url %}<img class="avatar-img" loading="lazy" decoding="async" width="74" height="74" src="{{ member.image_url }}" alt="{{ member.name }}" onerror="this.remove()">{% endif %}{{ member.initials }}</div>\n'
                  '            <h4>{{ member.name }}</h4>\n'
                  '            <div class="member-role">{{ member.role }}</div>\n'
                  '          </div>\n'
                  '          {% endfor %}\n'
                  '        </div>\n'
                  '        {% endfor %}')
home = home[:c_first] + committee_loop + home[c_end:]
home = home.replace("Photos coming soon", "{{ site.committee_note }}")

# ---- sponsors ----
spon_halves = re.findall(r'<div class="sponsors-half">.*?</div>', home, flags=re.DOTALL)
assert len(spon_halves) == 2
seed_sponsors = []
for cls, nm in re.findall(r'<span class="partner( partner-surprise)?">(.*?)</span>', spon_halves[0]):
    if (nm, bool(cls)) not in [(s["name"], s["surprise"]) for s in seed_sponsors]:
        seed_sponsors.append({"name": nm, "surprise": bool(cls)})
spon_loop = ('<div class="sponsors-half">\n'
             '          {% for sponsor in sponsors %}<span class="partner{% if sponsor.is_surprise %} partner-surprise{% endif %}">{% if not sponsor.is_surprise %}{{ sponsor.name }}{% else %}{{ sponsor.name }}{% endif %}</span>{% endfor %}\n'
             '        </div>')
home = re.sub(r'<div class="sponsors-half">.*?</div>', spon_loop, home, flags=re.DOTALL)
home = home.replace("Our Sponsors", "Our Sponsors")

# ---- FAQ ----
faq_items = extract_cards(home, '<div class="faq-item"')
assert len(faq_items) == 6, len(faq_items)
seed_faqs = []
for item in faq_items:
    q = re.search(r'<span class="faq-q-num">.*?</span>(.*?)</span>', item, re.DOTALL).group(1).strip()
    a = re.search(r'<div class="faq-a-inner"><p>(.*?)</p></div>', item, re.DOTALL).group(1).strip()
    seed_faqs.append({"q": q, "a": a})
f_first = home.find('<div class="faq-item"')
_, f_end = balanced_div(home, home.rfind('<div class="faq-item"'))
faq_loop = ('{% for faq in faqs %}\n'
            '          <div class="faq-item" data-reveal>\n'
            '            <button class="faq-q" onclick="toggleFaq(this)" aria-expanded="false">\n'
            '              <span><span class="faq-q-num">{{ forloop.counter|stringformat:"02d" }}&nbsp;/&nbsp;</span>{{ faq.question }}</span>\n'
            '              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>\n'
            '            </button>\n'
            '            <div class="faq-a"><div class="faq-a-inner"><p>{{ faq.answer }}</p></div></div>\n'
            '          </div>\n'
            '          {% endfor %}')
home = home[:f_first] + faq_loop + home[f_end:]

# ---- CA section ----
home = home.replace("Represent BBCC ICT Fest 2026 at your school or college. Lead promotions, build your network, and earn exclusive perks — certificate, crest, and priority access on fest day.",
                    "{{ site.ca_description }}")
home = home.replace("Become a <span class=\"gradient-text\">Campus Ambassador</span>",
                    "{{ site.ca_heading|default:'Become a Campus Ambassador' }}")
home = home.replace("Fill out the Google Form — takes under 2 minutes.",
                    "Fill out the online form — takes under 2 minutes.")
home = strip_google_links(home)

# ---- CTA ----
cta_m = re.search(r'<section class="section cta".*?</section>', home, flags=re.DOTALL)
assert cta_m
cta = cta_m.group(0)
cta = re.sub(r'<span class="section-tag">.*?</span>', '<span class="section-tag">{{ site.cta_tag }}</span>', cta, count=1)
cta = cta.replace("Ready to Be Part of<br><span class=\"gradient-text\">The Biggest ICT Fest?</span>",
                  "{{ site.cta_title_a }}<br><span class=\"gradient-text\">{{ site.cta_title_b }}</span>")
cta = re.sub(r'<p class="cta-sub">.*?</p>', '<p class="cta-sub">{{ site.cta_subtitle }}</p>', cta, flags=re.DOTALL, count=1)
cta_actions = re.search(r'<div class="cta-actions" data-reveal>.*?</div>\s*</div>', cta, flags=re.DOTALL)
assert cta_actions
new_actions = ("""<div class="cta-actions" data-reveal>
          {% for event in events|slice:":3" %}
          <a href="{{ event.get_absolute_url }}" class="btn {% if forloop.counter == 1 %}btn-primary{% elif forloop.counter == 2 %}btn-primary btn-gold{% else %}btn-outline{% endif %}" data-magnetic>
            Register for {{ event.name }}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:15px;height:15px;"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
          </a>
          {% endfor %}
          <a href="{% url 'registrations:ca_apply' %}" class="btn btn-outline" data-magnetic style="border-color: var(--ember-line); color: var(--ember);">
            Become Campus Ambassador
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width:15px;height:15px;"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
          </a>
        </div>""")
cta = cta[:cta_actions.start()] + new_actions + cta[cta_actions.end():]
home = home[:cta_m.start()] + cta + home[cta_m.end():]

# ---- NEW sections: reviews / volunteers preview / blog (same design language) ----
new_sections = """
    <!-- REVIEWS -->
    <section class="section" id="reviews" style="background: var(--bg); border-top: 1px solid var(--line); border-bottom: 1px solid var(--line);">
      <div class="container">
        <div class="section-header" data-reveal>
          <span class="section-tag">Reviews</span>
          <h2 class="section-title">What People<br><span class="gradient-text">Say About Us</span></h2>
          <p class="section-desc">{% if rating_count %}<span class="stars">★★★★★</span> {{ rating_avg }}/5 from {{ rating_count }} review{{ rating_count|pluralize }}{% else %}Be the first to review BBCC ICT Fest 2026.{% endif %}</p>
        </div>
        <div class="reviews-grid">
          {% for review in reviews|slice:":6" %}
          <div class="review-card" data-reveal>
            <div class="stars">{% for i in "12345" %}{% if forloop.counter <= review.rating %}★{% else %}☆{% endif %}{% endfor %}</div>
            <p>"{{ review.comment|truncatewords:40 }}"</p>
            <div class="review-who">
              <div class="review-ava">{% if review.user.profile.avatar_url %}<img src="{{ review.user.profile.avatar_url }}" alt="{{ review.user.username }}">{% else %}{{ review.user.username|slice:":2"|upper }}{% endif %}</div>
              <div><b>{{ review.user.get_full_name|default:review.user.username }}</b><span>{{ review.updated_at|date:"M j, Y" }}</span></div>
            </div>
          </div>
          {% empty %}
          <div class="review-card" data-reveal><p>No reviews yet — share your experience after logging in.</p></div>
          {% endfor %}
        </div>
        <div style="text-align:center; margin-top: 36px;" data-reveal>
          {% if user.is_authenticated %}
          <a href="{% url 'core:review_write' %}" class="btn btn-outline" data-magnetic>Write a Review</a>
          {% else %}
          <a href="{% url 'accounts:login' %}?next={% url 'core:review_write' %}" class="btn btn-outline" data-magnetic>Login to Review</a>
          {% endif %}
          <a href="{% url 'core:reviews' %}" class="btn btn-primary" data-magnetic style="margin-left:10px;">All Reviews</a>
        </div>
      </div>
    </section>

    <!-- VOLUNTEERS PREVIEW -->
    <section class="section" id="volunteers" style="background: var(--bg-2); border-bottom: 1px solid var(--line);">
      <div class="container">
        <div class="section-header" data-reveal>
          <span class="section-tag">Volunteers</span>
          <h2 class="section-title">Powered by<br><span class="gradient-text">Volunteers</span></h2>
          <p class="section-desc">The students working behind the scenes to make the fest unforgettable.</p>
        </div>
        <div class="committee-grid">
          {% for v in volunteers_preview %}
          <div class="member-card" data-reveal>
            <div class="member-photo">{% if v.image_url %}<img class="avatar-img" loading="lazy" decoding="async" width="74" height="74" src="{{ v.image_url }}" alt="{{ v.name }}" onerror="this.remove()">{% endif %}{{ v.initials }}</div>
            <h4>{{ v.name }}</h4>
            <div class="member-role">{{ v.role }}</div>
          </div>
          {% empty %}
          <p class="committee-note" data-reveal>Volunteer list coming soon.</p>
          {% endfor %}
        </div>
        <div style="text-align:center; margin-top: 36px;" data-reveal>
          <a href="{% url 'volunteers:list' %}" class="btn btn-outline" data-magnetic>Meet All Volunteers</a>
        </div>
      </div>
    </section>

    <!-- BLOG PREVIEW -->
    <section class="section" id="blog" style="background: var(--bg); border-bottom: 1px solid var(--line);">
      <div class="container">
        <div class="section-header" data-reveal>
          <span class="section-tag">Blog</span>
          <h2 class="section-title">Stories &amp;<br><span class="gradient-text">Announcements</span></h2>
          <p class="section-desc">Latest updates from the fest team.</p>
        </div>
        <div class="comp-grid">
          {% for post in latest_posts %}
          <div class="comp-card" data-reveal>
            {% if post.cover_image_url %}<img class="blog-cover" loading="lazy" src="{{ post.cover_image_url }}" alt="{{ post.title }}">{% endif %}
            <h3>{{ post.title }}</h3>
            <p class="comp-desc">{{ post.excerpt|default:post.content|truncatewords:24 }}</p>
            <div class="comp-details">
              <div class="comp-detail"><span class="blog-meta">{{ post.published_at|date:"M j, Y" }} · {{ post.likes_count }} likes</span></div>
            </div>
            <div style="margin-top:16px;"><a href="{{ post.get_absolute_url }}" class="btn btn-outline btn-sm" data-magnetic>Read More</a></div>
          </div>
          {% empty %}
          <div class="comp-card" data-reveal><h3>Coming soon</h3><p class="comp-desc">Our first stories are on the way.</p></div>
          {% endfor %}
        </div>
        <div style="text-align:center; margin-top: 36px;" data-reveal>
          <a href="{% url 'blog:list' %}" class="btn btn-outline" data-magnetic>Visit the Blog</a>
        </div>
      </div>
    </section>
"""
home = home.rstrip() + "\n" + new_sections
assert "docs.google.com" not in home, "google form links remain!"

# ---------------------------------------------------------------- 5. FOOTER
footer = re.search(r'<footer class="footer".*?</footer>', html, flags=re.DOTALL).group(0)
footer = footer.replace('href="#top"', 'href="{% url \'core:home\' %}#top"')
footer = footer.replace('<img src="logo.png"', '<img src="{% static \'img/logo.png\' %}"')
footer = footer.replace("BBCC ICT Fest 2026\n          </a>", "{{ site.site_name }}\n          </a>")
footer = footer.replace("The Biggest ICT Festival in Tangail District. Organized by Bindubasini Boys' Computer Club bringing technology and innovation to the forefront of education.",
                        "{{ site.footer_about }}")
footer = re.sub(r'href="#(about|competitions|timeline|guests|committee|campus-ambassador)"',
                "href=\"{% url 'core:home' %}#\\1\"", footer)
footer = footer.replace('href="games/index.html">Games</a>',
                        'href="{% url \'core:arcade\' %}">Games</a></div>\n          <div class="footer-col">\n'
                        '            <h5>More</h5>\n'
                        '            <a href="{% url \'core:reviews\' %}">Reviews</a>\n'
                        '            <a href="{% url \'volunteers:list\' %}">Volunteers</a>\n'
                        '            <a href="{% url \'blog:list\' %}">Blog</a>\n'
                        '            <a href="{% url \'registrations:events\' %}">Register</a>\n'
                        '            <a href="{% url \'registrations:ca_apply\' %}">Campus Ambassador</a>\n'
                        '          </div>')
footer = footer.replace("club.bbcc@gmail.com", "{{ site.contact_email }}")
footer = footer.replace("https://www.facebook.com/bbcompuerclub", "{{ site.facebook_url }}")
footer = footer.replace("https://mdsalehin.netlify.app/", "{{ site.made_by_url }}")
footer = footer.replace(">Made by Md Abu Salehin</a>", ">Made by {{ site.made_by_name }}</a>")
assert "docs.google.com" not in footer

# ---------------------------------------------------------------- 6. ASSEMBLE base.html + home.html
base = f"""{{% load static pwa %}}
<!DOCTYPE html>
<html lang="en">
<head>{head}
</head>
<body>

  <div class="grain" aria-hidden="true"></div>
  <div id="progressBar" aria-hidden="true"></div>
  <div id="cursorGlow" aria-hidden="true"></div>

  <!-- PRELOADER -->
  <div class="preloader" id="preloader" aria-hidden="true">
    <div class="pre-logo"><img src="{{% static 'img/logo.png' %}}" alt=""></div>
    <div class="pre-text">booting ict fest 2026<span>...</span></div>
    <div class="pre-bar"><div class="pre-bar-fill"></div></div>
  </div>

  {{% block nav %}}
{nav_new}
  {{% endblock nav %}}

  {{% if messages %}}
  <div class="container"><div class="django-messages" style="padding-top: calc(var(--nav-h) + 18px);">{{% for message in messages %}}<div class="django-message {{{{ message.tags }}}}">{{{{ message }}}}</div>{{% endfor %}}</div></div>
  {{% endif %}}

  <main id="top">
  {{% block content %}}{{% endblock %}}
  </main>

  {{% block footer %}}
{footer}
  {{% endblock footer %}}

  <!-- BACK TO TOP -->
  <button class="to-top" id="toTop" aria-label="Back to top">
    <svg class="to-top-progress" viewBox="0 0 52 52"><circle cx="26" cy="26" r="24"/></svg>
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5"/><path d="m5 12 7-7 7 7"/></svg>
  </button>

  <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/ScrollTrigger.min.js"></script>
  <script src="{{% static 'js/main.js' %}}"></script>
  {{% block extra_js %}}{{% endblock %}}
</body>
</html>
"""
(TEMPLATES / "base.html").write_text(base, encoding="utf-8")
(TEMPLATES / "core").mkdir(parents=True, exist_ok=True)
(TEMPLATES / "core" / "home.html").write_text(
    '{% extends "base.html" %}\n{% block content %}\n' + home.strip() + "\n{% endblock %}\n",
    encoding="utf-8",
)

# ---------------------------------------------------------------- 7. SEED JSON
import json

chips = re.findall(r'<div class="hero-chip chip-\d+">(.*?)</div>', html, flags=re.DOTALL)
ticker_raw = re.findall(r'<span class="ticker-item">(.*?)</span>', halves[0])
stats = [(int(v), sfx, lbl) for v, sfx, lbl in
         re.findall(r'<div class="about-stat"><div class="about-stat-num"><span data-count="(\d+)">0</span>(.*?)</div><div class="about-stat-label">(.*?)</div></div>', html, flags=re.DOTALL)]

comp_slugs = ["ict-quiz", "science-showdown", "coding", "chess", "rubiks-cube"]
for comp, slug in zip(seed_competitions, comp_slugs):
    comp["slug"] = slug

def img_url(src):
    """Legacy local image -> absolute static URL (editable URLField value)."""
    if not src or src.startswith(("http", "{%")):
        return src or ""
    rel = src.replace("../", "")
    if (ROOT / rel).exists():
        # images/* and games/* ship as static dirs, so images/members/x.jpg
        # is served at /static/members/x.jpg.
        static_rel = rel
        if static_rel.startswith("images/"):
            static_rel = static_rel[len("images/"):]
        return "https://bbccictfest.pro.bd/static/" + static_rel
    return ""

for g in seed_guests:
    g["image_url"] = img_url(g.pop("image"))
cat_slugs = ["advisers", "segment-heads", "executive-committee", "executive-members"]
seed_committee_out = []
for cat, slug in zip(seed_committee, cat_slugs):
    members = [{"name": m["name"], "role": m["role"], "image_url": img_url(m["image"])} for m in cat["members"]]
    seed_committee_out.append({"name": cat["name"], "slug": slug, "members": members})

seed = {
    "chips": [{"html": c.strip(), "css_class": f"chip-{i + 1}"} for i, c in enumerate(chips)],
    "ticker": [t.strip() for t in ticker_raw],
    "stats": [{"value": v, "suffix": s.strip(), "label": l.strip()} for v, s, l in stats],
    "competitions": seed_competitions,
    "timeline": seed_timeline,
    "guests": seed_guests,
    "committee": seed_committee_out,
    "sponsors": seed_sponsors,
    "faqs": seed_faqs,
}
(SCRIPTS / "seed_data.json").write_text(json.dumps(seed, indent=2, ensure_ascii=False), encoding="utf-8")
print("wrote base.html, home.html, main.css/js, seed_data.json")
print("guests:", len(seed_guests), "| committee cats:", len(seed_committee_out),
      "| faqs:", len(seed_faqs), "| sponsors:", len(seed_sponsors))

