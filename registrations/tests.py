from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Role
from core.models import PersonReview
from schools.models import School

User = get_user_model()


def make_ca_user(username, school, first_name="Test", last_name="Ambassador"):
    """Ambassadors are plain users with the Campus Ambassador role + school,
    created by organizers in admin — there is no application flow."""
    user = User.objects.create_user(username=username, password="pass12345")
    user.first_name = first_name
    user.last_name = last_name
    user.save()
    profile = user.profile
    profile.role = Role.CAMPUS_AMBASSADOR
    profile.school = school
    profile.save()
    return user


class AmbassadorReviewTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Test School")
        self.user = User.objects.create_user(username="rater", password="pass12345")
        self.other = User.objects.create_user(username="rater2", password="pass12345")
        self.ambassador = make_ca_user("causer", self.school)
        self.review_url = f"/register/ca/{self.ambassador.pk}/review/"
        self.delete_url = f"/register/ca/{self.ambassador.pk}/review/delete/"

    def test_detail_public_shows_reviews(self):
        PersonReview.objects.create(
            user=self.other, ambassador_user=self.ambassador, rating=5, comment="Great CA!"
        )
        r = self.client.get(f"/register/ca/{self.ambassador.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Great CA!")
        self.assertContains(r, "Test Ambassador")
        self.assertContains(r, "Login")

    def test_list_links_to_detail(self):
        r = self.client.get("/register/ca/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f"/register/ca/{self.ambassador.pk}/")

    def test_non_ca_user_has_no_detail_page(self):
        plain = User.objects.create_user(username="plain", password="pass12345")
        r = self.client.get(f"/register/ca/{plain.pk}/")
        self.assertEqual(r.status_code, 404)

    def test_non_ca_user_has_no_qr_pages(self):
        plain = User.objects.create_user(username="plainqr", password="pass12345")
        self.assertEqual(
            self.client.get(f"/register/ca/{plain.pk}/qr.png").status_code, 404
        )
        self.assertEqual(
            self.client.get(f"/register/ca/{plain.pk}/qr-download/").status_code, 404
        )

    def test_review_requires_login(self):
        r = self.client.post(self.review_url, {"rating": 5, "comment": "Nice!"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r.url)
        self.assertFalse(PersonReview.objects.exists())

    def test_create_and_edit_single_review_per_ambassador(self):
        self.client.login(username="rater", password="pass12345")
        r = self.client.post(self.review_url, {"rating": 5, "comment": "First!"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(
            PersonReview.objects.filter(user=self.user, ambassador_user=self.ambassador).count(), 1
        )
        self.client.post(self.review_url, {"rating": 2, "comment": "Updated"})
        self.assertEqual(
            PersonReview.objects.filter(user=self.user, ambassador_user=self.ambassador).count(), 1
        )
        review = PersonReview.objects.get(user=self.user, ambassador_user=self.ambassador)
        self.assertEqual((review.rating, review.comment), (2, "Updated"))
        self.assertIsNone(review.volunteer)

    def test_delete_own_review(self):
        PersonReview.objects.create(
            user=self.user, ambassador_user=self.ambassador, rating=4, comment="Bye"
        )
        self.client.login(username="rater", password="pass12345")
        r = self.client.post(self.delete_url)
        self.assertEqual(r.status_code, 302)
        self.assertFalse(
            PersonReview.objects.filter(user=self.user, ambassador_user=self.ambassador).exists()
        )

    def test_sitemap_includes_ambassador_detail(self):
        r = self.client.get("/sitemap.xml")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f"/register/ca/{self.ambassador.pk}/")


class AmbassadorListTests(TestCase):
    def test_ca_list_grouped_by_school(self):
        first_school = School.objects.create(name="Test School")
        make_ca_user("firstca", first_school, first_name="First", last_name="CA")
        other_school = School.objects.create(name="Second School", order=1)
        make_ca_user("otherca", other_school, first_name="Second", last_name="CA")
        r = self.client.get("/register/ca/")
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        self.assertIn("Test School", content)
        self.assertIn("Second School", content)
        self.assertIn("First CA", content)
        self.assertIn("Second CA", content)
        self.assertIn("2 ambassadors", content)

    def test_apply_url_is_gone(self):
        self.assertEqual(self.client.get("/register/ca/apply/").status_code, 404)
