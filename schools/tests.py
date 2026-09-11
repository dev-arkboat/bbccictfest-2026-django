from django.apps import apps
from django.test import TestCase


class SchoolsAppTests(TestCase):
    def test_app_installed(self):
        self.assertTrue(apps.is_installed("schools"))
