from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import PersonReview

from .models import Volunteer

User = get_user_model()


class VolunteerReviewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rater", password="pass12345")
        self.other = User.objects.create_user(username="rater2", password="pass12345")
        self.volunteer = Volunteer.objects.create(name="Test Volunteer", role="Volunteer")
        self.volunteer2 = Volunteer.objects.create(name="Second Volunteer", role="Volunteer")
        self.review_url = f"/volunteers/{self.volunteer.pk}/review/"
        self.delete_url = f"/volunteers/{self.volunteer.pk}/review/delete/"

    def test_detail_shows_reviews_publicly(self):
        PersonReview.objects.create(
            user=self.other, volunteer=self.volunteer, rating=5, comment="Great work!"
        )
        r = self.client.get(self.volunteer.get_absolute_url())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Great work!")
        self.assertContains(r, "Login")

    def test_review_requires_login(self):
        r = self.client.post(self.review_url, {"rating": 5, "comment": "Nice!"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r.url)
        self.assertFalse(PersonReview.objects.exists())

    def test_create_and_edit_single_review_per_volunteer(self):
        self.client.login(username="rater", password="pass12345")
        r = self.client.post(self.review_url, {"rating": 5, "comment": "First!"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(
            PersonReview.objects.filter(user=self.user, volunteer=self.volunteer).count(), 1
        )
        r = self.client.post(self.review_url, {"rating": 3, "comment": "Updated"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(
            PersonReview.objects.filter(user=self.user, volunteer=self.volunteer).count(), 1
        )
        review = PersonReview.objects.get(user=self.user, volunteer=self.volunteer)
        self.assertEqual((review.rating, review.comment), (3, "Updated"))
        self.assertIsNone(review.ambassador)

    def test_same_user_can_review_different_volunteers(self):
        self.client.login(username="rater", password="pass12345")
        self.client.post(self.review_url, {"rating": 5, "comment": "One"})
        self.client.post(
            f"/volunteers/{self.volunteer2.pk}/review/", {"rating": 4, "comment": "Two"}
        )
        self.assertEqual(PersonReview.objects.filter(user=self.user).count(), 2)

    def test_invalid_rating_rejected(self):
        self.client.login(username="rater", password="pass12345")
        r = self.client.post(self.review_url, {"rating": 6, "comment": "Too high"})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(
            PersonReview.objects.filter(user=self.user, volunteer=self.volunteer).exists()
        )

    def test_delete_own_review(self):
        PersonReview.objects.create(
            user=self.user, volunteer=self.volunteer, rating=4, comment="Bye"
        )
        self.client.login(username="rater", password="pass12345")
        r = self.client.post(self.delete_url)
        self.assertEqual(r.status_code, 302)
        self.assertFalse(
            PersonReview.objects.filter(user=self.user, volunteer=self.volunteer).exists()
        )

    def test_rating_summary_shown(self):
        PersonReview.objects.create(
            user=self.user, volunteer=self.volunteer, rating=5, comment="A"
        )
        PersonReview.objects.create(
            user=self.other, volunteer=self.volunteer, rating=3, comment="B"
        )
        r = self.client.get(self.volunteer.get_absolute_url())
        self.assertContains(r, "4.0/5")
        self.assertContains(r, "2 ratings")
