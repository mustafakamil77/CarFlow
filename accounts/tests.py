from django.test import TestCase
from django.urls import reverse


class AuthTemplatesSmokeTests(TestCase):
    def test_login_template_renders(self):
        resp = self.client.get(reverse("login"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'name="viewport"')

