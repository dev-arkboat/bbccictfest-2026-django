"""End-to-end smoke tests for the BBCC ICT Fest 2026 dynamic site.

Registrations are offline-only: no public signup forms, no payment gateway.
Rows are created from the admin panel with a mandatory integer serial,
one-or-more segments (events), and an auto-calculated (but editable) amount.

Covers: home (offline messaging, no Google Forms), arcade pages,
offline registration info page, admin offline model behavior, single editable
review, blog comment/like, CA dashboards, profiles, sitemap/robots/PWA.
Run: uv run python manage.py test
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from schools.models import School

User = get_user_model()


class FestFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_site", verbosity=0)
        cls.school = School.objects.create(name="Test School")
        cls.admin = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pass12345"
        )
        cls.user = User.objects.create_user(
            username="tester", email="t@example.com", password="pass12345"
        )

    # -- public pages -------------------------------------------------
    def test_home_no_google_forms(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("docs.google.com", r.content.decode())
        self.assertIn("ICT FEST", r.content.decode())

    def test_home_shows_offline_registration(self):
        r = self.client.get("/")
        content = r.content.decode()
        self.assertIn("Registrations Are Offline Only", content)
        self.assertNotIn("Register Now", content)
        self.assertNotIn("Register for ", content)

    def test_sponsors_track_repeats_for_seamless_loop(self):
        # Each marquee half must repeat the sequence 3x (like the original
        # design) so the -50% loop stays seamless with few sponsors on file.
        import re

        from core.models import Sponsor

        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        section = re.search(
            r'<section class="sponsors".*?</section>', r.content.decode(), re.DOTALL
        )
        self.assertIsNotNone(section)
        for sponsor in Sponsor.objects.filter(is_active=True):
            # 3x per half x 2 halves
            self.assertEqual(section.group(0).count(sponsor.name), 6, sponsor.name)

    def test_arcade_and_all_games(self):
        r = self.client.get("/games/")
        self.assertEqual(r.status_code, 200)
        from core.models import Game

        slugs = list(Game.objects.filter(is_active=True).values_list("slug", flat=True))
        self.assertGreaterEqual(len(slugs), 15)
        for slug in slugs:
            rr = self.client.get(f"/games/{slug}/")
            self.assertEqual(rr.status_code, 200, f"game page {slug}")

    def test_pokemon_hub_label(self):
        # The pokemon hub aggregates 11 ROM variants; the bar must show the
        # hub name, not the first variant's title ("Pokémon Ruby").
        from core.models import Game

        poke = Game.objects.get(slug="pokemon")
        self.assertEqual(poke.title, "Pokémon")
        r = self.client.get("/games/snake/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, ">Pokémon</a>")
        self.assertNotContains(r, "Pokémon Ruby</a>")

    def test_static_pages(self):
        for url in ["/register/", "/blog/", "/volunteers/", "/reviews/",
                    "/robots.txt", "/sitemap.xml", "/manifest.json",
                    "/serviceworker.js", "/offline/",
                    "/accounts/signup/", "/accounts/login/"]:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
        sitemap = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("/games/snake/", sitemap)
        self.assertIn("/blog/", sitemap)

    # -- offline registration info page -------------------------------
    def test_register_page_is_offline_only(self):
        r = self.client.get("/register/")
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        self.assertIn("Registrations Are", content)
        self.assertIn("Offline Only", content)
        # No public form left: no segment checkboxes, no submit, no total JS.
        self.assertNotIn('name="events"', content)
        self.assertNotIn("Register & Continue", content)
        self.assertNotIn('id="fee-total"', content)
        # Segments are still listed for reference with fees.
        self.assertIn("ICT Quiz", content)

    def test_old_participant_urls_are_gone(self):
        from registrations.models import Event, Registration

        chess = Event.objects.get(slug="chess")
        reg = Registration.objects.create(
            serial_number=9001, full_name="Gone User", phone="01712345678",
            school=self.school, class_name="10",
            status=Registration.STATUS_CONFIRMED,
        )
        reg.events.add(chess)
        for url in [
            "/register/chess/register/",
            f"/register/r/{reg.pk}/",
            f"/register/r/{reg.pk}/receipt/",
            f"/register/r/{reg.pk}/pay/",
            f"/register/r/{reg.pk}/refresh/",
            f"/register/r/{reg.pk}/success/",
            f"/register/r/{reg.pk}/failed/",
            "/register/lookup/",
            "/register/my/",
            "/register/pay/callback/",
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404, url)

    # -- reviews -------------------------------------------------------
    def test_single_editable_review(self):
        self.client.login(username="tester", password="pass12345")
        r = self.client.post("/reviews/write/", {"rating": 5, "comment": "Amazing fest!"})
        self.assertEqual(r.status_code, 302)
        from core.models import Review

        self.assertEqual(Review.objects.filter(user=self.user).count(), 1)
        r = self.client.post("/reviews/write/", {"rating": 4, "comment": "Even better!"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Review.objects.filter(user=self.user).count(), 1)
        self.assertEqual(Review.objects.get(user=self.user).rating, 4)
        r = self.client.get("/reviews/")
        self.assertContains(r, "Even better!")

    # -- blog ----------------------------------------------------------
    def test_blog_comment_and_like(self):
        from blog.models import Post

        post = Post.objects.create(
            title="Hello Fest", content="Body here", author=self.admin,
            status=Post.STATUS_PUBLISHED,
        )
        self.assertEqual(self.client.get(f"/blog/{post.slug}/").status_code, 200)
        self.client.login(username="tester", password="pass12345")
        r = self.client.post(f"/blog/{post.slug}/comment/", {"body": "Great post!"})
        self.assertEqual(r.status_code, 302)
        self.assertContains(self.client.get(f"/blog/{post.slug}/"), "Great post!")
        self.client.post(f"/blog/{post.slug}/like/")
        post.refresh_from_db()
        self.assertEqual(post.likes_count(), 1)
        self.client.post(f"/blog/{post.slug}/like/")  # toggle off
        post.refresh_from_db()
        self.assertEqual(post.likes_count(), 0)

    # -- CA + profiles -------------------------------------------------
    # Ambassadors are plain users with the Campus Ambassador role, created
    # by organizers in admin — there is no application flow (/register/ca/apply/ 404s).
    def test_ca_apply_url_gone(self):
        self.client.login(username="tester", password="pass12345")
        self.assertEqual(self.client.get("/register/ca/apply/").status_code, 404)

    def test_profile_pages(self):
        self.client.login(username="tester", password="pass12345")
        self.assertEqual(self.client.get("/accounts/me/").status_code, 200)
        self.assertEqual(self.client.get("/accounts/u/tester/").status_code, 200)
        r = self.client.post("/accounts/me/edit/", {
            "phone": "01800000000", "institution": "New School",
            "class_name": "9", "bio": "Hi",
        })
        self.assertEqual(r.status_code, 302)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.institution, "New School")

    def test_roles_layering(self):
        from accounts.models import role_rank

        self.assertEqual(role_rank(self.admin), 4)
        self.assertEqual(role_rank(self.user), 0)
        # organizer-only board blocked for participants, ok for staff-made organizer
        self.assertEqual(self.client.get("/register/board/").status_code, 302)
        self.user.profile.role = "organizer"
        self.user.profile.save()
        self.user.refresh_from_db()
        self.assertEqual(role_rank(self.user), 3)


class SchoolVolunteerAmbassadorTests(TestCase):
    """Schools, volunteer QR pages, public ambassadors, CA dashboard."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_site", verbosity=0)
        from schools.models import School
        from volunteers.models import Volunteer

        cls.school = School.objects.create(name="Bindubasini Boys' School")
        cls.other_school = School.objects.create(name="Other School")
        cls.volunteer = Volunteer.objects.create(
            name="QR Tester", role="Volunteer — Logistics", school=cls.school
        )
        cls.other_volunteer = Volunteer.objects.create(
            name="Other Volunteer", role="Volunteer", school=cls.other_school
        )
        cls.user = User.objects.create_user(
            username="tester", email="t@example.com", password="pass12345"
        )
        cls.ca_user = User.objects.create_user(
            username="campusca", email="ca@example.com", password="pass12345"
        )

    def _approve_ca(self, user, school):
        """Make a user a Campus Ambassador the admin way: role + school."""
        from accounts.models import Role

        user.first_name = "CA"
        user.last_name = "Person"
        user.save()
        profile = user.profile
        profile.role = Role.CAMPUS_AMBASSADOR
        profile.school = school
        profile.save()
        return user

    def _make_registration(self, event_slug, serial, name, school, **kw):
        from registrations.models import Event, Registration

        event = Event.objects.get(slug=event_slug)
        reg = Registration.objects.create(
            serial_number=serial, full_name=name,
            email=kw.get("email", f"{serial}@example.com"),
            phone=kw.get("phone", "01711111111"),
            school=school, class_name=kw.get("class_name", "10"),
            status=kw.get("status", Registration.STATUS_CONFIRMED),
            amount_bdt=kw.get("amount_bdt", 0),
        )
        reg.events.add(event)
        if not reg.amount_bdt:
            reg.amount_bdt = reg.calculated_amount
            reg.save(update_fields=["amount_bdt", "updated_at"])
        return reg

    # -- volunteer detail + QR (public, no login) ------------------------
    def test_volunteer_detail_public(self):
        r = self.client.get(f"/volunteers/{self.volunteer.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "QR Tester")
        self.assertContains(r, "Download QR Code")

    def test_volunteer_qr_png_public(self):
        r = self.client.get(f"/volunteers/{self.volunteer.pk}/qr.png")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/png")
        self.assertTrue(r.content.startswith(b"\x89PNG"))

    def test_volunteer_qr_download_public(self):
        r = self.client.get(f"/volunteers/{self.volunteer.pk}/qr-download/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/png")
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertIn(f"volunteer-{self.volunteer.pk}-qr.png", r["Content-Disposition"])

    def test_volunteer_list_links_to_detail(self):
        r = self.client.get("/volunteers/")
        self.assertContains(r, f"/volunteers/{self.volunteer.pk}/")

    # -- ambassador detail + QR (public, no login) -----------------------
    def test_ambassador_detail_public(self):
        ca = self._approve_ca(self.ca_user, self.school)
        r = self.client.get(f"/register/ca/{ca.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "CA Person")
        self.assertContains(r, "Download QR Code")

    def test_ambassador_qr_png_public(self):
        ca = self._approve_ca(self.ca_user, self.school)
        r = self.client.get(f"/register/ca/{ca.pk}/qr.png")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/png")
        self.assertTrue(r.content.startswith(b"\x89PNG"))

    def test_ambassador_qr_download_public(self):
        ca = self._approve_ca(self.ca_user, self.school)
        r = self.client.get(f"/register/ca/{ca.pk}/qr-download/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/png")
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertIn(f"ambassador-{ca.pk}-qr.png", r["Content-Disposition"])

    def test_ambassador_qr_matches_volunteer_qr_format(self):
        """Same generator, same PNG profile as the volunteer QR."""
        ca = self._approve_ca(self.ca_user, self.school)
        r_ca = self.client.get(f"/register/ca/{ca.pk}/qr.png")
        r_vol = self.client.get(f"/volunteers/{self.volunteer.pk}/qr.png")
        self.assertEqual(r_ca["Content-Type"], r_vol["Content-Type"])
        self.assertTrue(r_ca.content.startswith(b"\x89PNG"))
        self.assertTrue(r_vol.content.startswith(b"\x89PNG"))

    # -- reviews visible to everyone -------------------------------------
    def test_reviews_visible_anonymously(self):
        from core.models import Review

        Review.objects.create(user=self.user, rating=5, comment="Publicly visible!")
        r = self.client.get("/reviews/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Publicly visible!")
        # anonymous visitors are pointed at login to write one
        self.assertContains(r, "Login to Review")
        self.client.login(username="tester", password="pass12345")
        r = self.client.get("/reviews/")
        self.assertContains(r, "Edit Your Review")

    # -- ambassadors section ----------------------------------------------
    def test_ambassador_list_public(self):
        self._approve_ca(self.ca_user, self.school)
        r = self.client.get("/register/ca/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "CA Person")
        self.assertContains(r, self.school.name)

    def test_ca_without_school_cannot_use_dashboard(self):
        from accounts.models import Role

        profile = self.ca_user.profile
        profile.role = Role.CAMPUS_AMBASSADOR
        profile.school = None
        profile.save()
        self.client.login(username="campusca", password="pass12345")
        r = self.client.get("/register/ca/dashboard/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/me/", r.url)

    # -- CA dashboard ------------------------------------------------------
    def test_ca_dashboard_requires_login(self):
        r = self.client.get("/register/ca/dashboard/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r.url)

    def test_ca_dashboard_blocked_for_non_ca(self):
        self.client.login(username="tester", password="pass12345")
        r = self.client.get("/register/ca/dashboard/")
        self.assertEqual(r.status_code, 302)

    def test_ca_rank_between_volunteer_and_organizer(self):
        from accounts.models import role_rank

        self._approve_ca(self.ca_user, self.school)
        self.assertEqual(role_rank(self.ca_user), 2)
        # CAs get their school dashboard but not organizer pages.
        self.client.login(username="campusca", password="pass12345")
        self.assertEqual(self.client.get("/register/board/").status_code, 302)

    def test_ca_dashboard_shows_own_school_volunteers(self):
        self._approve_ca(self.ca_user, self.school)
        self.client.login(username="campusca", password="pass12345")
        r = self.client.get("/register/ca/dashboard/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.school.name)
        self.assertContains(r, "QR Tester")
        self.assertNotContains(r, "Other Volunteer")

    def test_review_form_renders_five_blank_stars(self):
        self.client.login(username="tester", password="pass12345")
        r = self.client.get("/reviews/write/")
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        self.assertIn('class="star-rating"', content)
        self.assertEqual(content.count("★"), 5)
        self.assertNotIn("checked", content)

    def test_sitemap_includes_volunteers_and_ambassadors(self):
        sitemap = self.client.get("/sitemap.xml").content.decode()
        self.assertIn(f"/volunteers/{self.volunteer.pk}/", sitemap)
        self.assertIn("/register/ca/", sitemap)

    def test_ca_dashboard_shows_only_own_school_participants(self):
        self._approve_ca(self.ca_user, self.school)
        self._make_registration("chess", 9101, "Own Pupil", self.school)
        self._make_registration("chess", 9102, "Other Pupil", self.other_school)
        self.client.login(username="campusca", password="pass12345")
        r = self.client.get("/register/ca/dashboard/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Own Pupil")
        self.assertNotContains(r, "Other Pupil")

    def test_ca_dashboard_participant_search(self):
        self._approve_ca(self.ca_user, self.school)
        self._make_registration("chess", 9201, "Searchable One", self.school)
        self._make_registration("chess", 9202, "Unrelated Kid", self.school)
        self.client.login(username="campusca", password="pass12345")
        r = self.client.get("/register/ca/dashboard/", {"q": "Searchable"})
        self.assertContains(r, "Searchable One")
        self.assertNotContains(r, "Unrelated Kid")


class OfflineRegistrationModelTests(TestCase):
    """Admin-entered offline rows: serial rules, segments, auto amount."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_site", verbosity=0)
        cls.school = School.objects.create(name="Offline School")

    def _events(self, *slugs):
        from registrations.models import Event

        return [Event.objects.get(slug=s) for s in slugs]

    def test_serial_required_unique_integer(self):
        from django.db import IntegrityError

        from registrations.models import Registration

        field = Registration._meta.get_field("serial_number")
        self.assertIsInstance(field, __import__("django.db.models", fromlist=["PositiveIntegerField"]).PositiveIntegerField)
        self.assertTrue(field.unique)
        self.assertFalse(field.null)
        self.assertFalse(field.blank)
        # missing serial -> validation error via form
        from registrations.forms import RegistrationAdminForm

        chess = self._events("chess")[0]
        form = RegistrationAdminForm(data={
            "full_name": "No Serial", "phone": "01712345678",
            "school": self.school.pk, "class_name": "10",
            "events": [chess.pk], "amount_bdt": 0,
            "status": Registration.STATUS_PENDING,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("serial_number", form.errors)
        # duplicate serial rejected
        reg = Registration.objects.create(
            serial_number=5001, full_name="First", phone="01712345678",
            school=self.school, class_name="10",
        )
        reg.events.add(chess)
        with self.assertRaises(IntegrityError):
            dup = Registration.objects.create(
                serial_number=5001, full_name="Dupe", phone="01812345678",
                school=self.school, class_name="10",
            )
            dup.events.add(chess)

    def test_no_institution_field(self):
        from registrations.models import Registration

        names = {f.name for f in Registration._meta.get_fields()}
        self.assertNotIn("institution", names)
        self.assertNotIn("group_id", names)
        self.assertNotIn("bkash_payment_id", names)
        self.assertNotIn("bkash_trx_id", names)

    def test_school_always_required(self):
        from django.db.models import PROTECT

        from registrations.forms import RegistrationAdminForm
        from registrations.models import Registration

        field = Registration._meta.get_field("school")
        self.assertFalse(field.null)
        self.assertFalse(field.blank)
        self.assertEqual(field.remote_field.on_delete, PROTECT)
        # missing school -> validation error via form
        chess = self._events("chess")[0]
        form = RegistrationAdminForm(data={
            "serial_number": 5201, "full_name": "No School",
            "phone": "01712345678",
            "class_name": "10", "events": [chess.pk],
            "amount_bdt": 0, "status": Registration.STATUS_PENDING,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("school", form.errors)

    def test_segments_addable_and_amount_auto_calculates(self):
        from registrations.forms import RegistrationAdminForm
        from registrations.models import Registration

        chess, coding = self._events("chess", "coding")
        # amount 0 -> auto-fills with summed fees
        form = RegistrationAdminForm(data={
            "serial_number": 5101, "full_name": "Multi Seg",
            "phone": "01712345678", "school": self.school.pk,
            "class_name": "10", "events": [chess.pk, coding.pk],
            "amount_bdt": 0, "status": Registration.STATUS_PENDING,
        })
        self.assertTrue(form.is_valid(), form.errors)
        reg = form.save()
        self.assertEqual(reg.amount_bdt, chess.fee_bdt + coding.fee_bdt)
        self.assertEqual(set(reg.events.all()), {chess, coding})
        # manual override preserved
        form2 = RegistrationAdminForm(data={
            "serial_number": 5102, "full_name": "Manual Amt",
            "phone": "01712345678", "school": self.school.pk,
            "class_name": "10", "events": [coding.pk],
            "amount_bdt": 100, "status": Registration.STATUS_PAID,
        })
        self.assertTrue(form2.is_valid(), form2.errors)
        reg2 = form2.save()
        self.assertEqual(reg2.amount_bdt, 100)

    def test_payment_status_choices_have_no_gateway_state(self):
        from registrations.models import Registration

        values = {v for v, _ in Registration.STATUS_CHOICES}
        self.assertNotIn("payment_pending", values)
        self.assertIn("paid", values)
        self.assertIn("pending", values)


class VerifyPageTests(TestCase):
    """Fest-day gate tool: search everything, filter, check in."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_site", verbosity=0)
        cls.school = School.objects.create(name="Gate School")
        cls.other_school = School.objects.create(name="Far School")
        cls.staff = User.objects.create_user(username="gate", password="pass12345")
        cls.staff.profile.role = "volunteer"
        cls.staff.profile.save()
        cls.plain = User.objects.create_user(username="plain", password="pass12345")
        from registrations.models import Event, Registration

        chess = Event.objects.get(slug="chess")
        coding = Event.objects.get(slug="coding")
        cls.r1 = Registration.objects.create(
            serial_number=7001,
            full_name="Gate Test", email="gate@example.com",
            phone="01712345678", school=cls.school,
            class_name="10",
            status=Registration.STATUS_CONFIRMED,
        )
        cls.r1.events.add(chess)
        cls.r2 = Registration.objects.create(
            serial_number=7002,
            full_name="Second Person", email="second@example.com",
            phone="01899999999", school=cls.other_school,
            class_name="9", status=Registration.STATUS_PAID,
        )
        cls.r2.events.add(coding)

    def test_access_control(self):
        r = self.client.get("/register/verify/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r.url)
        self.client.login(username="plain", password="pass12345")
        r = self.client.get("/register/verify/")
        self.assertEqual(r.status_code, 302)
        self.client.login(username="gate", password="pass12345")
        r = self.client.get("/register/verify/")
        self.assertEqual(r.status_code, 200)

    def test_search_every_field(self):
        self.client.login(username="gate", password="pass12345")
        cases = [
            "01712345678",      # phone
            "01712-345678",     # phone, formatted
            self.r1.reference,  # reference number
            self.r1.reference.lower().replace("bbcc26-", ""),  # bare digits
            "7001",             # serial number
            "Gate Test",        # name
            "Gate School",      # school
            "gate@example.com", # email
            "Class 10",         # class display value
        ]
        for term in cases:
            with self.subTest(term=term):
                r = self.client.get("/register/verify/", {"q": term})
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, "Gate Test")
        r = self.client.get("/register/verify/", {"q": "Second Person"})
        self.assertNotContains(r, "Gate Test")

    def test_filters(self):
        from registrations.models import Registration

        self.client.login(username="gate", password="pass12345")
        chess_id = str(self.r1.events.first().pk)
        r = self.client.get("/register/verify/", {"event": chess_id})
        self.assertContains(r, "Gate Test")
        self.assertNotContains(r, "Second Person")
        r = self.client.get("/register/verify/", {"status": "paid"})
        self.assertContains(r, "Second Person")
        self.assertNotContains(r, "Gate Test")
        r = self.client.get("/register/verify/", {"school": str(self.school.pk)})
        self.assertContains(r, "Gate Test")
        self.assertNotContains(r, "Second Person")

    def test_row_shows_school_segments_and_amount(self):
        self.r2.amount_bdt = self.r2.calculated_amount
        self.r2.save(update_fields=["amount_bdt", "updated_at"])
        self.client.login(username="gate", password="pass12345")
        r = self.client.get("/register/verify/")
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        # mandatory school, multi-segment names, and fee cross-check column
        self.assertContains(r, "Gate School")
        self.assertContains(r, "Chess")
        self.assertContains(r, "Coding Competition")
        self.assertContains(r, f"{self.r2.amount_bdt} BDT")
        self.assertContains(r, "Free")  # chess row has amount 0

    def test_check_in_toggle(self):
        from registrations.models import Registration

        self.client.login(username="gate", password="pass12345")
        r = self.client.post(
            f"/register/r/{self.r1.pk}/check-in/",
            {"next": "/register/verify/?q=Gate"},
        )
        self.assertEqual(r.status_code, 302)
        self.assertIn("/register/verify/?q=Gate", r.url)
        self.r1.refresh_from_db()
        self.assertTrue(self.r1.checked_in)
        self.assertIsNotNone(self.r1.checked_in_at)
        r = self.client.get("/register/verify/", {"checked_in": "1"})
        self.assertContains(r, "Gate Test")
        self.client.post(f"/register/r/{self.r1.pk}/check-in/", {"next": "/register/verify/"})
        self.r1.refresh_from_db()
        self.assertFalse(self.r1.checked_in)
        self.assertIsNone(self.r1.checked_in_at)

    def test_check_in_requires_post_and_role(self):
        self.client.login(username="gate", password="pass12345")
        r = self.client.get(f"/register/r/{self.r1.pk}/check-in/")
        self.assertEqual(r.status_code, 405)
        self.client.login(username="plain", password="pass12345")
        r = self.client.post(f"/register/r/{self.r1.pk}/check-in/")
        self.assertEqual(r.status_code, 302)


class SetupProductionTests(TestCase):
    """Production bootstrap: full content seed + env-driven admin user."""

    def test_missing_password_refuses(self):
        import os
        from unittest import mock

        from django.core.management.base import CommandError

        with mock.patch.dict(os.environ):
            os.environ.pop("DJANGO_SUPERUSER_PASSWORD", None)
            with self.assertRaises(CommandError):
                call_command("setup_production", verbosity=0)

    def test_creates_admin_and_seeds_everything(self):
        from unittest import mock

        from core.models import Competition, FAQ, Game, SiteSetting
        from registrations.models import Event as RegEvent

        env = {
            "DJANGO_SUPERUSER_USERNAME": "boss",
            "DJANGO_SUPERUSER_EMAIL": "boss@example.com",
            "DJANGO_SUPERUSER_PASSWORD": "s3cure-pass",
        }
        with mock.patch.dict("os.environ", env, clear=False):
            call_command("setup_production", verbosity=0)
        boss = User.objects.get(username="boss")
        self.assertTrue(boss.is_staff and boss.is_superuser)
        self.assertTrue(boss.check_password("s3cure-pass"))
        self.assertTrue(self.client.login(username="boss", password="s3cure-pass"))
        # every content family present
        self.assertTrue(SiteSetting.objects.exists())
        self.assertTrue(Competition.objects.exists())
        self.assertTrue(Game.objects.exists())
        self.assertTrue(RegEvent.objects.filter(is_active=True).exists())
        self.assertTrue(FAQ.objects.exists())

    def test_idempotent_rerun_resets_password(self):
        from unittest import mock

        User.objects.create_superuser(
            username="boss", email="old@example.com", password="old-pass"
        )
        with mock.patch.dict(
            "os.environ",
            {"DJANGO_SUPERUSER_USERNAME": "boss", "DJANGO_SUPERUSER_PASSWORD": "new-pass"},
            clear=False,
        ):
            call_command("setup_production", verbosity=0)
        self.assertEqual(User.objects.filter(username="boss").count(), 1)
        boss = User.objects.get(username="boss")
        self.assertTrue(boss.check_password("new-pass"))
        self.assertFalse(boss.check_password("old-pass"))


class SettingsTests(SimpleTestCase):
    """Env parsing + database resolution (no DB needed)."""

    def test_env_bool(self):
        from bbccictfest_2026.settings import env_bool

        with mock.patch.dict("os.environ", {"T": "True", "F": "no", "N": "0"}, clear=False):
            self.assertTrue(env_bool("T", False))
            self.assertFalse(env_bool("F", True))
            self.assertFalse(env_bool("N", True))
            self.assertTrue(env_bool("MISSING", True))
            self.assertFalse(env_bool("MISSING", False))

    def test_env_list(self):
        from bbccictfest_2026.settings import env_list

        with mock.patch.dict(
            "os.environ", {"H": "a.example.com, b.example.com ,, "}, clear=False
        ):
            self.assertEqual(env_list("H"), ["a.example.com", "b.example.com"])
            self.assertEqual(env_list("MISSING", "x,y"), ["x", "y"])
            self.assertEqual(env_list("MISSING"), [])

    def test_resolve_databases_empty_gives_sqlite_file(self):
        from pathlib import Path

        from bbccictfest_2026.settings import _resolve_databases

        base = Path("/srv/app")
        dbs = _resolve_databases("", "db.sqlite3", base)
        self.assertEqual(dbs["default"]["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(dbs["default"]["NAME"], base / "db.sqlite3")

    def test_resolve_databases_sqlite_url(self):
        import os
        import tempfile
        from pathlib import Path

        from bbccictfest_2026.settings import _resolve_databases

        base = Path("/srv/app")
        dbs = _resolve_databases("sqlite:///custom.sqlite3", "db.sqlite3", base)
        self.assertEqual(dbs["default"]["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(dbs["default"]["NAME"], str(base / "custom.sqlite3"))
        abs_path = str(Path(tempfile.gettempdir()) / "bbcc-abs-test.sqlite3")
        dbs = _resolve_databases(
            "sqlite:///" + abs_path.replace("\\", "/"), "db.sqlite3", base
        )
        self.assertEqual(
            os.path.normpath(dbs["default"]["NAME"]), os.path.normpath(abs_path)
        )
        dbs = _resolve_databases("sqlite://:memory:", "db.sqlite3", base)
        self.assertEqual(dbs["default"]["NAME"], ":memory:")

    def test_resolve_databases_postgres_url(self):
        from pathlib import Path

        from bbccictfest_2026.settings import _resolve_databases

        dbs = _resolve_databases(
            "postgres://u:pw@db.example.com:5432/fest", "db.sqlite3", Path("/srv/app")
        )
        default = dbs["default"]
        self.assertEqual(default["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(default["NAME"], "fest")
        self.assertEqual(default["USER"], "u")
        self.assertEqual(default["HOST"], "db.example.com")
        self.assertEqual(default["PORT"], 5432)
        self.assertGreater(default["CONN_MAX_AGE"], 0)
