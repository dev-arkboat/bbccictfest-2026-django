# BBCC ICT Fest 2026

The official website for **BBCC ICT Fest 2026** — the biggest ICT festival in the
Tangail district, organized by the Bindubasini Boys' Computer Club.

What started as a static site is now a full Django web app: students can register
and pay with bKash, schools manage their teams through Campus Ambassadors,
volunteers get their own QR-coded profile pages, and visitors can read the blog,
play arcade games, and leave reviews. Organizers run all of it from a themed
admin panel — no code changes needed.

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
- [Create an account](https://bbccictfest.pro.bd/accounts/signup/) and [register for events](https://bbccictfest.pro.bd/register/) —
  free events confirm instantly, paid ones check out securely with bKash
- Track everything from [your dashboard](https://bbccictfest.pro.bd/accounts/me/): registrations, payments,
  CA application, liked posts, and your review — plus a public profile page to share
- Leave a 5-star [review](https://bbccictfest.pro.bd/reviews/) of the fest (one per person — you can edit it anytime),
  and rate individual volunteers and ambassadors right on their pages
- Apply to be a [Campus Ambassador](https://bbccictfest.pro.bd/register/ca/apply/) for your school

**If you're organizing**
- Run the whole fest from `/admin/`: events and fees, registrations, payments,
  schools, volunteers, ambassadors, blog posts, reviews, and every line of
  homepage text
- Give organizers the `Organizer` group and volunteers the `Volunteer` group —
  permissions follow a simple ladder: participant < volunteer < organizer < superuser

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
| `registrations` | Events, registrations, bKash payment ledger, Campus Ambassador applications |
| `schools` | School directory — every CA belongs to one, volunteers group under theirs |
| `volunteers` | Volunteer profiles, public pages, QR codes |
| `blog` | Posts, comments, likes |
| `accounts` | Sign up / login / profiles, role ladder (`Organizer` / `Volunteer` groups) |

Static game files live in `games/` and are served as static assets; every page
template extends `base.html` (arcade pages go through `arcade/base.html`), so
the design stays consistent everywhere.

---

## Payments with bKash (the important part 💸)

We use [`pybkash`](https://github.com/Itsmmdoha/pybkash) for tokenized checkout.
The flow is deliberately paranoid, in this order:

1. `create_payment` → redirect the student to their `bkash_url`
2. bKash sends them back to `/register/pay/callback/?paymentID=…&status=…`
3. The callback parameters are treated as a **hint only** — never trusted
4. The server calls `execute_payment`, then double-checks with `query_payment`
5. The paid amount is compared against the registration amount before anything
   is marked paid

Every step lands in an append-only `PaymentTransaction` row, so any payment can
be audited, retried, or reconciled from the admin later. Callbacks are
idempotent — a double-hit just re-verifies.

**Try it locally without credentials:**

```env
BKASH_MOCK=True
```

Mock mode simulates the entire flow end-to-end. For real money, fill in your
merchant credentials and flip it off:

```env
BKASH_USERNAME=...
BKASH_PASSWORD=...
BKASH_APP_KEY=...
BKASH_APP_SECRET=...
BKASH_SANDBOX=True      # False in production
BKASH_MOCK=False
BKASH_CALLBACK_BASE=https://bbccictfest.pro.bd
```

Background reading: the
[pybkash repo](https://github.com/Itsmmdoha/pybkash),
[PyPI page](https://pypi.org/project/pybkash/), and this
[integration walkthrough](https://dev.to/itsmmdoha/how-to-integrate-bkash-payment-gateway-in-python-the-easy-way-1997).

---

## Schools, ambassadors & volunteers 🤝

This is the people system that holds the fest together:

1. **Add the school** in admin (Schools → Add). One row per school/college.
2. A student **applies as Campus Ambassador** and *must* pick their school.
3. An organizer **approves** the application in admin.
4. **Assign volunteers** to the same school on their volunteer records.
5. The approved CA logs in and opens their **school dashboard**
   (`/register/ca/dashboard/`) — they see their school and everyone
   volunteering under it, with contact info for coordination.

The public [ambassadors page](https://bbccictfest.pro.bd/register/ca/) only ever shows *approved*
ambassadors, and the dashboard is fenced so a CA can only ever see their own
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
| `BKASH_*` | Payment credentials (see above) |

---

## Testing & quality

```powershell
uv run python manage.py test   # 37 tests: payments (mock), QR, roles, event + person reviews, blog, sitemap…
uv run python manage.py check  # Django system checks
```

`seed_site` is idempotent — run it any time to (re)create starter content and
auto-link schools from institutions already on file. It never touches user data.

---

## Going live checklist

- [ ] `DJANGO_DEBUG=False` and a strong, unique `DJANGO_SECRET_KEY`
- [ ] Real `SITE_URL` (+ `ALLOWED_HOSTS` if you serve extra domains)
- [ ] `DATABASE_URL` pointing at Postgres (SQLite is dev-only)
- [ ] `EMAIL_HOST` + credentials so the site can actually send mail
- [ ] `BKASH_MOCK=False`, `BKASH_SANDBOX=False`, production callback base URL —
      and the same callback URL whitelisted in your bKash merchant dashboard:
      `https://YOUR-DOMAIN/register/pay/callback/`
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

**Payments stuck at "pending"?**
Open the registration in admin and inspect its `PaymentTransaction` rows —
the raw gateway payloads will tell you exactly which step failed, and the
"Refresh status" button re-queries bKash.

**QR codes look broken?**
They're generated on the fly with `qrcode` + Pillow (both in
`pyproject.toml`). The detail page embeds `/volunteers/<id>/qr.png`, and the
download button serves the same PNG as an attachment.

---

Made with care by the Bindubasini Boys' Computer Club for the students of
Tangail. If something's off, open an issue — and if you're here to contribute,
`uv sync`, `migrate`, `seed_site`, and you're in. 💛
