from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Role
from schools.models import School

User = get_user_model()
CREATE_URL = "/register/ca/create/"


def make_user(username, password="pass12345", role=Role.PARTICIPANT):
    user = User.objects.create_user(username=username, password=password)
    profile = user.profile
    profile.role = role
    profile.save()
    return user


def ca_form_data(school, **overrides):
    data = {
        "username": "newca",
        "password1": "Str0ng!Passw0rd",
        "password2": "Str0ng!Passw0rd",
        "first_name": "New",
        "last_name": "Ambassador",
        "email": "newca@example.com",
        "phone": "01700000000",
        "school": school.pk,
        "bio": "Loves ICT.",
    }
    data.update(overrides)
    return data


class CampusAmbassadorCreateTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Test School")
        self.organizer = make_user("org", role=Role.ORGANIZER)
        self.participant = make_user("plain", role=Role.PARTICIPANT)

    def test_anonymous_redirected_to_login(self):
        r = self.client.get(CREATE_URL)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r.url)

    def test_participant_blocked(self):
        self.client.login(username="plain", password="pass12345")
        r = self.client.get(CREATE_URL)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, "/")

    def test_organizer_can_open(self):
        self.client.login(username="org", password="pass12345")
        r = self.client.get(CREATE_URL)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Create Ambassador")

    def test_create_success(self):
        self.client.login(username="org", password="pass12345")
        r = self.client.post(CREATE_URL, ca_form_data(self.school))
        user = User.objects.get(username="newca")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, f"/register/ca/{user.pk}/")
        self.assertTrue(user.check_password("Str0ng!Passw0rd"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.profile.role, Role.CAMPUS_AMBASSADOR)
        self.assertEqual(user.profile.school, self.school)
        self.assertEqual(user.profile.institution, "Test School")
        self.assertEqual(user.profile.phone, "01700000000")
        # new CA shows up publicly and can reach the dashboard
        self.assertContains(self.client.get("/register/ca/"), "New Ambassador")
        self.client.login(username="newca", password="Str0ng!Passw0rd")
        self.assertEqual(
            self.client.get("/register/ca/dashboard/").status_code, 200
        )

    def test_duplicate_username_rejected(self):
        make_user("newca")
        self.client.login(username="org", password="pass12345")
        r = self.client.post(CREATE_URL, ca_form_data(self.school))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "already taken")
        self.assertEqual(User.objects.filter(username="newca").count(), 1)

    def test_password_mismatch_rejected(self):
        self.client.login(username="org", password="pass12345")
        r = self.client.post(
            CREATE_URL, ca_form_data(self.school, password2="Different!1")
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "do not match")
        self.assertFalse(User.objects.filter(username="newca").exists())
