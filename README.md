# BBCC ICT Fest 2026

The official website for **BBCC ICT Fest 2026** — the biggest ICT festival in the
Tangail district, organized by the Bindubasini Boys' Computer Club.

What started as a static site is now a full Django web app: registrations are
offline-only (paper forms entered from the admin panel), schools manage their
teams through Campus Ambassadors, volunteers get their own QR-coded profile
pages, and visitors can read the blog, play arcade games, and leave reviews.
Organizers run all of it from a themed admin panel — no code changes needed.

🌐 **Live site:** https://bbccictfest.pro.bd

---

## What you can do here

**If you're visiting**
- Explore events, timeline, guests, committee, sponsors, and FAQs on the homepage
- Meet the [volunteers](https://bbccictfest.pro.bd/volunteers/) — every volunteer has a public profile page
  with a downloadable QR code that links straight back to it, plus 5-star ratings from visitors
- Meet the [Campus Ambassadors](https://bbccictfest.pro.bd/register/ca/) representing each school —
  each ambassador has a public page with ratings too
- Read [reviews](https://bbccictfest.pro.bd/reviews/) from past participants, and the [blog](https://bbccictfest.pro.bd/blog/)
- Kill time in the [BBCC Arcade](https://bbccictfest.pro.bd/games/) — 15 playable browser games

**If you're participating**
- Registrations are **offline only** — sign up on paper at your school or at the
  venue help desk. The [registration page](https://bbccictfest.pro.bd/register/)
  lists the segments and fees for reference.
- [Create an account](https://bbccictfest.pro.bd/accounts/signup/) to write reviews,
  rate volunteers/ambassadors, and follow the blog — no online signup needed.
- Track everything from [your dashboard](https://bbccictfest.pro.bd/accounts/me/):
  your offline registrations (added by organizers), liked posts, and your review —
  plus a public profile page to share
- Leave a 5-star [review](https://bbccictfest.pro.bd/reviews/) of the fest (one per person — you can edit it anytime),
  and rate individual volunteers and ambassadors right on their pages

**If you're organizing**
- Run the whole fest from `/admin/`: events and fees, offline registrations
  (serial number, segments, auto-calculated amount, payment status),
  schools, volunteers, ambassadors, blog posts, reviews, and every line of
  homepage text
- Give organizers the `Organizer` group and volunteers the `Volunteer` group —
  permissions follow a simple ladder: participant < volunteer < campus ambassador < organizer < superuser
- Create Campus Ambassadors from the Registrations Board (**Create Campus Ambassador** button, organizers only) —
  there is no public application form; each CA gets a login tied to exactly one school

---

## Quickstart

You'll need **Python 3.12+** and **[uv](https://docs.astral.sh/uv/)**.

```powershell
# 1. Install dependencies
uv sync

# 2. Configure your environment
copy .env.example .env
# For local play, the defaults just work (payments run in mock mode — see below)

# 3. Set up the database and starter content
uv run python manage.py migrate
uv run python manage.py seed_site

# 4. Create your admin account
uv run python manage.py createsuperuser

# 5. Run it
uv run python manage.py runserver
```

Open http://127.0.0.1:8000/ — and http://127.0.0.1:8000/admin/ for the control room.

> ⚠️ If a dev database with a default `admin` / `admin123` superuser is floating
> around from earlier setup, change that password immediately
> (`manage.py changepassword admin`). Never ship default credentials.

---

## How the pieces fit

| App | What it owns |
| --- | --- |
| `core` | Homepage CMS (hero, ticker, stats, competitions, timeline, guests, committee, sponsors, FAQ), reviews, arcade game catalog |
| `registrations` | Events (segments), offline registrations, Campus Ambassadors |
| `schools` | School directory — every CA belongs to one, volunteers group under theirs |
| `volunteers` | Volunteer profiles, public pages, QR codes |
| `blog` | Posts, comments, likes |
| `accounts` | Sign up / login / profiles, role ladder (`Organizer` / `Volunteer` groups) |

Static game files live in `games/` and are served as static assets; every page
template extends `base.html` (arcade pages go through `arcade/base.html`), so
the design stays consistent everywhere.

---

## Offline registrations 📝

There is no online signup and no payment gateway. Participants fill paper
forms at their school or the venue help desk. Organizers then enter each row
from `/admin/` → Registrations:

1. Type the paper **serial number** (required, unique integer).
2. Fill name, phone, school, class.
3. Tick one or more **segments** (events).
4. Leave **amount** at `0` to auto-calculate the summed segment fees, or type
   a value to override it manually.
5. Set the **payment status**: Pending / Paid / Confirmed / Cancelled.

Fest-day staff use `/register/verify/` to search by serial, reference
(`BBCC26-00001`), phone, name, school or class and tick check-in at the gate.

---

## Schools, ambassadors & volunteers 🤝

This is the people system that holds the fest together:

1. **Add the school** in admin (Schools → Add). One row per school/college.
2. An organizer **creates the ambassador** from the Registrations Board
   (**Create Campus Ambassador**) — username, school and password, no application form.
3. **Assign volunteers** to the same school on their volunteer records.
4. The CA logs in and opens their **school dashboard**
   (`/register/ca/dashboard/`) — they see their school and everyone
   volunteering under it, with contact info for coordination.

The public [ambassadors page](https://bbccictfest.pro.bd/register/ca/) only ever shows users
with the Campus Ambassador role, and the dashboard is fenced so a CA can only ever see their own
school's team.

---

## Configuration

All settings come from the environment (loaded from `.env` via
`python-dotenv` — never commit secrets). The full list with sane defaults is
in [`.env.example`](.env.example):

| Variable | What it does |
| --- | --- |
| `DJANGO_SECRET_KEY` | Signing key — generate a fresh one per environment |
| `DJANGO_DEBUG` | `True` = local dev setup, `False` = full production setup (closed hosts, HTTPS redirect + HSTS, secure cookies) |
| `DJANGO_ALLOWED_HOSTS` / `DJANGO_CSRF_TRUSTED_ORIGINS` | Your domain(s); in production they default to your `SITE_URL` host |
| `SITE_URL` | Canonical URL — used for sitemap, emails, QR codes |
| `DATABASE_URL` | Empty = local SQLite file. Set `postgres://USER:PASSWORD@HOST:5432/DBNAME` for Postgres (parsed by `dj-database-url`, persistent + health-checked connections) |
| `DJANGO_TIME_ZONE` | Fest timezone (`Asia/Dhaka`) |

---

## Testing & quality

```powershell
uv run python manage.py test   # offline registrations, QR, roles, reviews, blog, sitemap…
uv run python manage.py check  # Django system checks
```

`seed_site` is idempotent — run it any time to (re)create starter content.
It never touches user data.

---

## Going live checklist

- [ ] `DJANGO_DEBUG=False` and a strong, unique `DJANGO_SECRET_KEY`
- [ ] Real `SITE_URL` (+ `ALLOWED_HOSTS` if you serve extra domains)
- [ ] `DATABASE_URL` pointing at Postgres (SQLite is dev-only)
- [ ] `EMAIL_HOST` + credentials so the site can actually send mail
- [ ] `uv run python manage.py collectstatic` (WhiteNoise serves `/static/`)
- [ ] No default passwords left anywhere
- [ ] `sitemap.xml` / `robots.txt` resolve on your domain

### One-command production setup

On a fresh server, after `migrate`, a single command seeds every database
entry the site needs (all CMS content, events, games, schools, site domain)
and ensures the admin account — no interactive prompts, safe to re-run:

```powershell
$env:DJANGO_SUPERUSER_USERNAME="festadmin"
$env:DJANGO_SUPERUSER_EMAIL="club.bbcc@gmail.com"
$env:DJANGO_SUPERUSER_PASSWORD="use-a-strong-password-here"
uv run python manage.py setup_production
```

It refuses to run without `DJANGO_SUPERUSER_PASSWORD`, warns about `DEBUG`
being on or a default `SECRET_KEY`, and never touches registrations,
payments, reviews, or other user data — only starter content plus the one
admin user (re-running resets that user's password).

---

## Troubleshooting

**`DisallowedHost: 'testserver'` in the shell?**
The Django shell doesn't allow the test client host. In tests we use
`override_settings(ALLOWED_HOSTS=…)` — do the same in your script, or add the
host to `ALLOWED_HOSTS` temporarily.

**Background `runserver` dies between terminal sessions?**
Each shell session cleans up its child jobs. Run the server in a foreground
terminal (or a process manager) instead of a background job.

**Amount looks wrong on a registration?**
Open the row in admin — the total auto-calculates from the ticked segments
when the amount is left at `0`. Type any other value to keep a manual
override.

**QR codes look broken?**
They're generated on the fly with `qrcode` + Pillow (both in
`pyproject.toml`). The detail page embeds `/volunteers/<id>/qr.png`, and the
download button serves the same PNG as an attachment.

---

Made with care by the Bindubasini Boys' Computer Club for the students of
Tangail. If something's off, open an issue — and if you're here to contribute,
`uv sync`, `migrate`, `seed_site`, and you're in. 💛
