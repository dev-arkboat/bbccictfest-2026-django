from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import PersonReview
from schools.models import School

from .models import CampusAmbassadorApplication

User = get_user_model()


def make_ambassador(user, school, name="Test Ambassador", status="approved"):
    return CampusAmbassadorApplication.objects.create(
        user=user,
        school=school,
        full_name=name,
        email="ca@example.com",
        phone="01700000000",
        institution=school.name,
        class_name="10",
        motivation="Lead my campus!",
        status=status,
    )


class AmbassadorReviewTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Test School")
        self.user = User.objects.create_user(username="rater", password="pass12345")
        self.other = User.objects.create_user(username="rater2", password="pass12345")
        self.ca_user = User.objects.create_user(username="causer", password="pass12345")
        self.ambassador = make_ambassador(self.ca_user, self.school)
        self.review_url = f"/register/ca/{self.ambassador.pk}/review/"
        self.delete_url = f"/register/ca/{self.ambassador.pk}/review/delete/"

    def test_detail_public_shows_reviews(self):
        PersonReview.objects.create(
            user=self.other, ambassador=self.ambassador, rating=5, comment="Great CA!"
        )
        r = self.client.get(self.ambassador.get_absolute_url())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Great CA!")
        self.assertContains(r, "Login")

    def test_list_links_to_detail(self):
        r = self.client.get("/register/ca/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.ambassador.get_absolute_url())

    def test_pending_ambassador_has_no_detail_page(self):
        pending_user = User.objects.create_user(username="pending", password="pass12345")
        pending = make_ambassador(pending_user, self.school, name="Pending CA", status="pending")
        r = self.client.get(f"/register/ca/{pending.pk}/")
        self.assertEqual(r.status_code, 404)

    def test_pending_ambassador_has_no_qr_pages(self):
        pending_user = User.objects.create_user(username="pendingqr", password="pass12345")
        pending = make_ambassador(pending_user, self.school, name="Pending QR", status="pending")
        self.assertEqual(
            self.client.get(f"/register/ca/{pending.pk}/qr.png").status_code, 404
        )
        self.assertEqual(
            self.client.get(f"/register/ca/{pending.pk}/qr-download/").status_code, 404
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
            PersonReview.objects.filter(user=self.user, ambassador=self.ambassador).count(), 1
        )
        self.client.post(self.review_url, {"rating": 2, "comment": "Updated"})
        self.assertEqual(
            PersonReview.objects.filter(user=self.user, ambassador=self.ambassador).count(), 1
        )
        review = PersonReview.objects.get(user=self.user, ambassador=self.ambassador)
        self.assertEqual((review.rating, review.comment), (2, "Updated"))
        self.assertIsNone(review.volunteer)

    def test_delete_own_review(self):
        PersonReview.objects.create(
            user=self.user, ambassador=self.ambassador, rating=4, comment="Bye"
        )
        self.client.login(username="rater", password="pass12345")
        r = self.client.post(self.delete_url)
        self.assertEqual(r.status_code, 302)
        self.assertFalse(
            PersonReview.objects.filter(user=self.user, ambassador=self.ambassador).exists()
        )

    def test_sitemap_includes_ambassador_detail(self):
        r = self.client.get("/sitemap.xml")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f"/register/ca/{self.ambassador.pk}/")


class CampusAmbassadorFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="applicant", password="pass12345")

    def test_motivation_labelled_about_you(self):
        self.client.login(username="applicant", password="pass12345")
        r = self.client.get("/register/ca/apply/")
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        self.assertIn("About You", content)
        self.assertNotIn(">Motivation<", content)

    def test_institution_not_asked_but_mirrored_from_school(self):
        from .forms import CampusAmbassadorForm

        self.assertNotIn("institution", CampusAmbassadorForm.base_fields)
        school = School.objects.create(name="Mirrored School")
        self.client.login(username="applicant", password="pass12345")
        r = self.client.post("/register/ca/apply/", {
            "full_name": "Applicant", "email": "a@example.com", "phone": "01712345678",
            "school": school.pk, "class_name": "10", "district": "Tangail",
            "motivation": "I love tech fests!",
        })
        self.assertEqual(r.status_code, 200)
        from .models import CampusAmbassadorApplication

        app = CampusAmbassadorApplication.objects.get(user=self.user)
        self.assertEqual(app.institution, "Mirrored School")

    def test_ca_list_grouped_by_school(self):
        first_school = School.objects.create(name="Test School")
        first_user = User.objects.create_user(username="firstca", password="pass12345")
        make_ambassador(first_user, first_school, name="First CA")
        other_school = School.objects.create(name="Second School", order=1)
        other_user = User.objects.create_user(username="otherca", password="pass12345")
        make_ambassador(other_user, other_school, name="Second CA")
        r = self.client.get("/register/ca/")
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        self.assertIn("Test School", content)
        self.assertIn("Second School", content)
        self.assertIn("First CA", content)
        self.assertIn("Second CA", content)
        self.assertIn("2 ambassadors", content)
