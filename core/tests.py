"""End-to-end smoke tests for the BBCC ICT Fest 2026 dynamic site.

Covers: home (no Google Forms left), arcade pages, registration +
mock-bKash payment flow, single editable review, blog comment/like,
CA application, profiles, sitemap/robots/PWA.
Run: uv run python manage.py test
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase, override_settings

from schools.models import School

User = get_user_model()


@override_settings(BKASH_MOCK=True)
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

    # -- registration + mock bKash ------------------------------------
    def _register(self, slug, data):
        r = self.client.post(f"/register/{slug}/register/", data)
        self.assertIn(r.status_code, (302, 200), f"{slug}: {r.status_code}")
        return r

    def base_data(self, **kw):
        d = {
            "full_name": "Test User", "email": "t@example.com",
            "phone": "01712345678", "school": self.school.pk, "class_name": "10",
        }
        d.update(kw)
        return d

    def test_free_event_confirms_instantly(self):
        self.client.login(username="tester", password="pass12345")
        r = self._register("chess", self.base_data())
        self.assertEqual(r.status_code, 302)
        from registrations.models import Registration

        reg = Registration.objects.get(user=self.user, event__slug="chess")
        self.assertEqual(reg.status, Registration.STATUS_CONFIRMED)
        self.assertEqual(reg.user, self.user)

    def test_paid_event_mock_bkash_end_to_end(self):
        self.client.login(username="tester", password="pass12345")
        r = self._register("coding", self.base_data())
        self.assertEqual(r.status_code, 302)
        from registrations.models import Registration

        reg = Registration.objects.get(user=self.user, event__slug="coding")
        self.assertEqual(reg.status, Registration.STATUS_PAYMENT_PENDING)

        pay_url = f"/register/r/{reg.pk}/pay/"
        r = self.client.get(pay_url)
        self.assertEqual(r.status_code, 200)
        reg.refresh_from_db()
        self.assertTrue(reg.bkash_payment_id.startswith("MOCK-"))

        cb = f"/register/pay/callback/?paymentID={reg.bkash_payment_id}&status=success"
        r = self.client.get(cb)
        self.assertEqual(r.status_code, 302)
        reg.refresh_from_db()
        self.assertTrue(reg.is_paid, reg.status)
        self.assertTrue(reg.bkash_trx_id)
        self.assertIn("success", r.url)

        # idempotent re-hit
        r = self.client.get(cb)
        reg.refresh_from_db()
        self.assertTrue(reg.is_paid)

    def test_cancel_callback_marks_failed(self):
        self.client.login(username="tester", password="pass12345")
        self._register("ict-quiz", self.base_data())
        from registrations.models import Registration

        reg = Registration.objects.get(user=self.user, event__slug="ict-quiz")
        self.client.get(f"/register/r/{reg.pk}/pay/")
        reg.refresh_from_db()
        r = self.client.get(
            f"/register/pay/callback/?paymentID={reg.bkash_payment_id}&status=cancel"
        )
        self.assertEqual(r.status_code, 302)
        self.assertIn("failed", r.url)
        reg.refresh_from_db()
        self.assertFalse(reg.is_paid)

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
        from registrations.models import Event, Registration

        self._approve_ca(self.ca_user, self.school)
        chess = Event.objects.get(slug="chess")
        Registration.objects.create(
            event=chess, full_name="Own Pupil", email="own@example.com",
            phone="01711111111", school=self.school, institution=self.school.name,
            class_name="10", status=Registration.STATUS_CONFIRMED,
        )
        Registration.objects.create(
            event=chess, full_name="Other Pupil", email="other@example.com",
            phone="01822222222", school=self.other_school,
            institution=self.other_school.name,
            class_name="9", status=Registration.STATUS_CONFIRMED,
        )
        self.client.login(username="campusca", password="pass12345")
        r = self.client.get("/register/ca/dashboard/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Own Pupil")
        self.assertNotContains(r, "Other Pupil")

    def test_ca_dashboard_participant_search(self):
        from registrations.models import Event, Registration

        self._approve_ca(self.ca_user, self.school)
        chess = Event.objects.get(slug="chess")
        Registration.objects.create(
            event=chess, full_name="Searchable One", email="one@example.com",
            phone="01711111111", school=self.school, institution=self.school.name,
            class_name="10", status=Registration.STATUS_CONFIRMED,
        )
        Registration.objects.create(
            event=chess, full_name="Unrelated Kid", email="two@example.com",
            phone="01822222222", school=self.school, institution=self.school.name,
            class_name="9", status=Registration.STATUS_CONFIRMED,
        )
        self.client.login(username="campusca", password="pass12345")
        r = self.client.get("/register/ca/dashboard/", {"q": "Searchable"})
        self.assertContains(r, "Searchable One")
        self.assertNotContains(r, "Unrelated Kid")


@override_settings(BKASH_MOCK=True)
class GuestRegistrationTests(TestCase):
    """Registration without login: receipt via session, lookup via number+phone."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_site", verbosity=0)
        cls.school = School.objects.create(name="Guest School")

    def guest_data(self, **kw):
        d = {
            "full_name": "Guest User", "email": "guest@example.com",
            "phone": "01712345678", "school": self.school.pk, "class_name": "10",
        }
        d.update(kw)
        return d

    def test_guest_free_registration_shows_receipt(self):
        from registrations.models import Registration

        r = self.client.get("/register/chess/register/")
        self.assertEqual(r.status_code, 200)
        r = self.client.post("/register/chess/register/", self.guest_data())
        self.assertEqual(r.status_code, 302)
        reg = Registration.objects.get(event__slug="chess")
        self.assertIsNone(reg.user)
        self.assertIn(f"/register/r/{reg.pk}/receipt/", r.url)
        r = self.client.get(f"/register/r/{reg.pk}/receipt/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, reg.reference)
        self.assertContains(r, "Guest User")

    def test_receipt_session_gated(self):
        from registrations.models import Registration

        self.client.post("/register/chess/register/", self.guest_data())
        reg = Registration.objects.get(event__slug="chess")
        stranger = Client()
        r = stranger.get(f"/register/r/{reg.pk}/receipt/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/register/lookup/", r.url)

    def test_lookup_success_wrong_phone_and_unknown(self):
        from registrations.models import Registration

        self.client.post("/register/chess/register/", self.guest_data())
        reg = Registration.objects.get(event__slug="chess")
        # correct number + phone (formatted differently is fine)
        r = self.client.post("/register/lookup/", {
            "reference": reg.reference.lower(), "phone": "01712-345678",
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Guest User")
        self.assertContains(r, reg.reference)
        # wrong phone
        r = self.client.post("/register/lookup/", {
            "reference": reg.reference, "phone": "01999999999",
        })
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Guest User")
        self.assertContains(r, "No registration found")
        # unknown number
        r = self.client.post("/register/lookup/", {
            "reference": "BBCC26-99999", "phone": "01712345678",
        })
        self.assertContains(r, "No registration found")

    def test_duplicate_phone_email_registrations_allowed(self):
        from registrations.models import Registration

        self.client.post("/register/chess/register/", self.guest_data())
        self.client.post("/register/chess/register/", self.guest_data())
        self.assertEqual(
            Registration.objects.filter(
                event__slug="chess", phone="01712345678", email="guest@example.com"
            ).count(), 2,
        )

    def test_guest_paid_flow_mock_bkash_end_to_end(self):
        from registrations.models import Registration

        r = self.client.post("/register/coding/register/", self.guest_data())
        self.assertEqual(r.status_code, 302)
        reg = Registration.objects.get(event__slug="coding")
        self.assertIsNone(reg.user)
        r = self.client.get(f"/register/r/{reg.pk}/pay/")
        self.assertEqual(r.status_code, 200)
        reg.refresh_from_db()
        cb = f"/register/pay/callback/?paymentID={reg.bkash_payment_id}&status=success"
        r = self.client.get(cb)
        self.assertEqual(r.status_code, 302)
        reg.refresh_from_db()
        self.assertTrue(reg.is_paid, reg.status)
        r = self.client.get(f"/register/r/{reg.pk}/success/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, reg.reference)


class RegisterStatusTests(TestCase):
    """SiteSetting.register_status on/off switch for registration pages."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_site", verbosity=0)
        cls.school = School.objects.create(name="Status School")

    def set_status(self, on):
        from core.models import SiteSetting

        site = SiteSetting.get_solo()
        site.register_status = on
        site.save(update_fields=["register_status"])

    def guest_data(self, **kw):
        d = {
            "full_name": "Status User", "email": "status@example.com",
            "phone": "01712345678", "school": self.school.pk, "class_name": "10",
        }
        d.update(kw)
        return d

    def test_notice_shown_and_forms_hidden_when_off(self):
        self.set_status(False)
        r = self.client.get("/register/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Registrations closed")
        self.assertContains(r, "find your registration")
        self.assertNotContains(r, "Register & Continue")
        r = self.client.get("/register/chess/register/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Registrations closed")
        self.assertNotContains(r, "Confirm Registration")

    def test_posts_blocked_when_off(self):
        from registrations.models import Registration

        self.set_status(False)
        r = self.client.post("/register/", {
            **self.guest_data(), "events": ["1"],
        })
        self.assertEqual(r.status_code, 302)
        self.assertIn("/register/", r.url)
        self.assertEqual(Registration.objects.count(), 0)
        chess = self._event_pk("chess")
        r = self.client.post(f"/register/chess/register/", self.guest_data())
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Registration.objects.count(), 0)

    def test_everything_back_when_on(self):
        from registrations.models import Registration

        self.set_status(False)
        self.set_status(True)
        r = self.client.get("/register/")
        self.assertNotContains(r, "Registrations closed")
        self.assertContains(r, "Register & Continue")
        r = self.client.post("/register/chess/register/", self.guest_data())
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Registration.objects.count(), 1)

    def _event_pk(self, slug):
        from registrations.models import Event

        return Event.objects.get(slug=slug).pk


@override_settings(BKASH_MOCK=True)
class MultiSegmentRegistrationTests(TestCase):
    """One form, many segments, one combined bKash payment."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_site", verbosity=0)
        cls.school = School.objects.create(name="Multi School")
        cls.user = User.objects.create_user(
            username="tester", email="t@example.com", password="pass12345"
        )

    def _pks(self, *slugs):
        from registrations.models import Event

        return [str(Event.objects.get(slug=s).pk) for s in slugs]

    def _personal(self, **kw):
        d = {
            "full_name": "Multi User", "email": "multi@example.com",
            "phone": "01712345678", "school": self.school.pk, "class_name": "10",
        }
        d.update(kw)
        return d

    def test_multi_page_has_checkboxes_total_and_dropdowns(self):
        r = self.client.get("/register/")
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        self.assertIn('name="events"', content)
        self.assertIn("data-fee", content)
        self.assertIn('id="fee-total"', content)
        self.assertIn('name="school"', content)
        self.assertIn("Class 6", content)
        self.assertIn("Other", content)

    def test_multi_guest_mixed_free_paid_single_payment(self):
        from registrations.models import PaymentTransaction, Registration

        r = self.client.post("/register/", {
            **self._personal(), "events": self._pks("chess", "coding"),
        })
        self.assertEqual(r.status_code, 302)
        rows = list(Registration.objects.order_by("pk"))
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0].group_id)
        self.assertEqual(rows[0].group_id, rows[1].group_id)
        self.assertIsNone(rows[0].user)
        self.assertEqual(rows[0].institution, "Multi School")
        chess = Registration.objects.get(event__slug="chess")
        coding = Registration.objects.get(event__slug="coding")
        self.assertEqual(chess.status, Registration.STATUS_CONFIRMED)
        self.assertEqual(coding.status, Registration.STATUS_PAYMENT_PENDING)
        self.assertIn(f"/register/r/{rows[0].pk}/pay/", r.url)
        r = self.client.get(f"/register/r/{rows[0].pk}/pay/")
        self.assertEqual(r.status_code, 200)
        txn = PaymentTransaction.objects.get()
        self.assertEqual(txn.amount_bdt, 49)
        self.assertEqual(txn.group_id, rows[0].group_id)
        cb = f"/register/pay/callback/?paymentID={txn.payment_id}&status=success"
        r = self.client.get(cb)
        self.assertEqual(r.status_code, 302)
        chess.refresh_from_db()
        coding.refresh_from_db()
        self.assertEqual(chess.status, Registration.STATUS_CONFIRMED)
        self.assertTrue(coding.is_paid)
        self.assertTrue(coding.bkash_trx_id)
        r = self.client.get(f"/register/r/{rows[0].pk}/success/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, chess.reference)
        self.assertContains(r, coding.reference)

    def test_multi_all_free_confirms_and_lists_numbers(self):
        from registrations.models import Registration

        r = self.client.post("/register/", {
            **self._personal(), "events": self._pks("chess", "rubiks-cube"),
        })
        self.assertEqual(r.status_code, 302)
        rows = list(Registration.objects.order_by("pk"))
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(x.status == Registration.STATUS_CONFIRMED for x in rows))
        r = self.client.get(r.url)
        for row in rows:
            self.assertContains(r, row.reference)

    def test_multi_skips_paid_event_for_logged_in_user(self):
        from registrations.models import PaymentTransaction, Registration

        self.client.login(username="tester", password="pass12345")
        self.client.post("/register/coding/register/", self._personal())
        reg = Registration.objects.get(event__slug="coding", user=self.user)
        self.client.get(f"/register/r/{reg.pk}/pay/")
        reg.refresh_from_db()
        self.client.get(
            f"/register/pay/callback/?paymentID={reg.bkash_payment_id}&status=success"
        )
        r = self.client.post("/register/", {
            **self._personal(), "events": self._pks("coding", "chess"),
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Registration.objects.filter(user=self.user).count(), 2)
        chess = Registration.objects.get(user=self.user, event__slug="chess")
        self.assertEqual(chess.status, Registration.STATUS_CONFIRMED)
        self.assertEqual(PaymentTransaction.objects.count(), 1)

    def test_school_required_and_class_validated(self):
        from registrations.models import Registration

        data = self._personal()
        del data["school"]
        r = self.client.post("/register/", {**data, "events": self._pks("chess")})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Registration.objects.count(), 0)
        r = self.client.post("/register/", {
            **self._personal(class_name="11"), "events": self._pks("chess"),
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Registration.objects.count(), 0)
        r = self.client.post("/register/", {
            **self._personal(), "events": [],
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Registration.objects.count(), 0)

    def test_team_event_registers_without_team_fields(self):
        # Team details are no longer collected on public forms (kept on the
        # model + admin only) — science showdown registers like any segment.
        from registrations.models import Registration

        r = self.client.post("/register/", {
            **self._personal(), "events": self._pks("science-showdown"),
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Registration.objects.count(), 1)
        reg = Registration.objects.get(event__slug="science-showdown")
        self.assertEqual(reg.status, Registration.STATUS_CONFIRMED)

    def test_serial_unique_on_single_form(self):
        from registrations.models import Registration

        Registration.objects.create(
            event_id=self._event_pk("chess"), full_name="Old", email="o@x.com",
            phone="01800000000", school=self.school, institution="Multi School",
            class_name="10", serial_number="OFF-1",
            status=Registration.STATUS_CONFIRMED,
        )
        data = self._personal(phone="01800000001", email="n@x.com")
        data["serial_number"] = "OFF-1"
        r = self.client.post("/register/chess/register/", data)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Registration.objects.count(), 1)
        data["serial_number"] = "OFF-2"
        r = self.client.post("/register/chess/register/", data)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(
            Registration.objects.filter(serial_number="OFF-2").exists()
        )

    def _event_pk(self, slug):
        from registrations.models import Event

        return Event.objects.get(slug=slug).pk


@override_settings(BKASH_MOCK=True)
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
            event=chess, full_name="Gate Test", email="gate@example.com",
            phone="01712345678", school=cls.school, institution="Gate School",
            class_name="10", serial_number="GATE-1",
            status=Registration.STATUS_CONFIRMED,
        )
        cls.r2 = Registration.objects.create(
            event=coding, full_name="Second Person", email="second@example.com",
            phone="01899999999", school=cls.other_school, institution="Far School",
            class_name="9", status=Registration.STATUS_PAID,
        )

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
        from registrations.models import Registration

        self.client.login(username="gate", password="pass12345")
        cases = [
            "01712345678",      # phone
            "01712-345678",     # phone, formatted
            self.r1.reference,  # reference number
            self.r1.reference.lower().replace("bbcc26-", ""),  # bare digits
            "GATE-1",           # serial number
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
        chess_id = str(Registration.objects.get(pk=self.r1.pk).event_id)
        r = self.client.get("/register/verify/", {"event": chess_id})
        self.assertContains(r, "Gate Test")
        self.assertNotContains(r, "Second Person")
        r = self.client.get("/register/verify/", {"status": "paid"})
        self.assertContains(r, "Second Person")
        self.assertNotContains(r, "Gate Test")
        r = self.client.get("/register/verify/", {"school": str(self.school.pk)})
        self.assertContains(r, "Gate Test")
        self.assertNotContains(r, "Second Person")

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
